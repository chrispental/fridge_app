"""Opt-in live checks; defaults to read-only probes. Scratch migrations are opt-in and always rolled back.

Run from backend: .venv/bin/python scripts/check_integrations.py
Configuration is read explicitly from ../.env. Credentials are never printed.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from app.config import Settings

values = dotenv_values(Path(__file__).resolve().parents[2] / '.env')
cfg = Settings(_env_file=Path(__file__).resolve().parents[2] / '.env')
results = {}

def check(name, callback):
    try:
        results[name] = callback()
    except Exception as exc:
        results[name] = {'ok': False, 'error_type': type(exc).__name__}

with httpx.Client(timeout=20) as client:
    def models():
        r=client.get(cfg.openrouter_base_url.rstrip('/')+'/models')
        r.raise_for_status()
        ids={m['id'] for m in r.json()['data']}
        return {'vision_available':cfg.openrouter_vision_model in ids,'meal_available':cfg.openrouter_meal_model in ids}
    check('openrouter_models', models)
    def keys():
        r=client.get(cfg.supabase_jwks_url);r.raise_for_status()
        return {'ok':bool(r.json().get('keys')), 'algorithms': sorted({k.get('alg','unknown') for k in r.json().get('keys',[])})}
    check('supabase_signing_keys',keys)
    def storage():
        r=client.get(cfg.supabase_base+'/storage/v1/bucket/'+cfg.supabase_storage_bucket,headers={'apikey':cfg.supabase_secret_key})
        return {'status':r.status_code,'private':r.status_code==200 and not r.json().get('public')}
    check('supabase_storage',storage)
    def auth():
        r=client.get(cfg.supabase_base+'/auth/v1/settings',headers={'apikey':values.get('VITE_SUPABASE_PUBLISHABLE_KEY','')})
        return {'status':r.status_code,'email_enabled':r.status_code==200 and r.json().get('external',{}).get('email')}
    check('supabase_auth',auth)

def database():
    eng=create_engine(cfg.database_url,connect_args={'connect_timeout':15})
    try:
        with eng.connect() as con:
            con.execute(text('SET TRANSACTION READ ONLY'))
            con.execute(text('SELECT 1'))
            version=con.execute(text('SELECT version_num FROM alembic_version')).scalar()
            rows=con.execute(text("SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).all()
            return {'ok':True,'migration':version,'rls':{name:enabled for name,enabled in rows}}
    finally:eng.dispose()
check('supabase_database',database)
print(json.dumps(results,indent=2))

if '--exercise' in sys.argv or '--cloud-only' in sys.argv:
    import io, secrets, time, uuid
    from PIL import Image, ImageDraw
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    for key, value in cfg.model_dump().items():
        setattr(settings, key, value)
    from app.auth import verify_supabase_jwt
    from app.database import Base
    from app import models as orm
    from app.services.blob_storage import SupabaseStorage
    from app.services.vision import preprocess, extract_items
    from app.services.meal_engine import suggest_meals
    from app.services.allergens import violates_allergies
    from app.schemas import MealSuggestion

    live = {}
    users = []
    objects = []
    admin_headers = {'apikey': cfg.supabase_secret_key}
    public_headers = {'apikey': values.get('VITE_SUPABASE_PUBLISHABLE_KEY', '')}
    storage_client = SupabaseStorage(cfg.supabase_url, cfg.supabase_secret_key, cfg.supabase_storage_bucket)
    def checked(response):
        response.raise_for_status()
        return response.json()
    try:
        with httpx.Client(timeout=30) as client:
            run_id = uuid.uuid4().hex
            sessions = []
            for suffix in ('a', 'b'):
                email = f'fridge-test-{run_id}-{suffix}@example.invalid'
                password = secrets.token_urlsafe(30)
                created = checked(client.post(cfg.supabase_base+'/auth/v1/admin/users', headers=admin_headers,
                    json={'email':email,'password':password,'email_confirm':True,'user_metadata':{'purpose':'fridge-reliability-integration-test'}}))
                users.append(created['id'])
                token = checked(client.post(cfg.supabase_base+'/auth/v1/token?grant_type=password',headers=public_headers,
                    json={'email':email,'password':password}))['access_token']
                user = verify_supabase_jwt(token)
                assert user.id == created['id']
                sessions.append({'id':user.id,'headers':{'Authorization':'Bearer '+token}})
            live['auth'] = {'created_test_users':len(users),'real_jwks_verification':True}

            fixture=Image.new('RGB',(700,450),'white')
            draw=ImageDraw.Draw(fixture)
            draw.text((30,30),'GROCERY RECEIPT\n\nMilk - 1 quart\n\nEggs - 12 pieces\n\nApples - 3 pieces',fill='black',font_size=30)
            raw=io.BytesIO();fixture.save(raw,format='JPEG')
            jpeg,data_url=preprocess(raw.getvalue())
            key=storage_client.save_image(jpeg,user_id=users[0]);objects.append(key)
            assert storage_client.load_image(key)==jpeg
            signed=storage_client.signed_url(key)
            assert signed and client.get(signed).content==jpeg
            anon=client.get(cfg.supabase_base+'/storage/v1/object/'+cfg.supabase_storage_bucket+'/'+key,headers=public_headers)
            assert anon.status_code != 200
            live['storage']={'upload_download_signed_url':True,'anonymous_read_denied':True}

            # Real Supabase tokens and photos through the actual HTTP routes, with
            # application rows isolated in SQLite. No production app startup.
            import logging
            from fastapi.testclient import TestClient
            from sqlalchemy.pool import StaticPool
            from app.main import app
            from app.database import get_db
            from app.services.blob_storage import get_blob_storage
            logging.disable(logging.INFO)  # signed URLs and auth tokens stay private
            eng=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
            Base.metadata.create_all(eng)
            factory=sessionmaker(bind=eng)
            def isolated_db():
                with factory() as db: yield db
            app.dependency_overrides[get_db]=isolated_db
            app.dependency_overrides[get_blob_storage]=lambda: storage_client
            # The image route calls the storage factory directly, so override its cache.
            from unittest.mock import patch
            try:
                with patch('app.routers.inventory.get_blob_storage',return_value=storage_client):
                    api=TestClient(app)
                    a,b=sessions
                    added=api.post('/api/inventory',headers=a['headers'],json={'name':'rice','quantity':1,'unit':'cup'})
                    assert added.status_code==201
                    assert api.get('/api/inventory',headers=b['headers']).json()==[]
                    assert api.patch('/api/inventory/'+str(added.json()['id']),headers=b['headers'],json={'quantity':99}).status_code==404
                    assert api.get('/api/inventory').status_code==401
                    with factory() as db:
                        batch=orm.ExtractionBatch(user_id=a['id'],image_key=key,status='pending_review')
                        db.add(batch);db.commit();batch_id=batch.id
                    photo_path=f'/api/inventory/extract/{batch_id}/image'
                    assert api.get(photo_path,headers=b['headers'],follow_redirects=False).status_code==404
                    photo=api.get(photo_path,headers=a['headers'],follow_redirects=False)
                    assert photo.status_code==302 and client.get(photo.headers['location']).content==jpeg
                    live['http_auth']={'real_token_inventory':True,'cross_user_rows_and_photos_denied':True,'authenticated_photo':True,'anonymous_denied':True}
            finally:
                app.dependency_overrides.clear()

            if '--exercise' in sys.argv:
                started=time.monotonic()
                extracted,_=extract_items(data_url)
                live['vision']={'seconds':round(time.monotonic()-started,1),'items':[{'name':i.name,'quantity':i.quantity,'unit':i.unit} for i in extracted]}
                assert any('milk' in i.name for i in extracted)
                with factory() as db:
                    db.add(orm.Preferences(user_id=users[0],household_size=2,allergies=['peanuts'],equipment=['stovetop'],pantry_staples=['salt','pepper']))
                    db.add_all([orm.InventoryItem(user_id=users[0],name=n,quantity=q,unit=u) for n,q,u in [('eggs',12,'piece'),('rice',4,'cup'),('spinach',8,'oz')]])
                    db.commit()
                    started=time.monotonic()
                    meals=suggest_meals(db,users[0],count=2,idea='Two quick dinners using eggs, rice and spinach.')
                    assert meals
                    assert all(not violates_allergies(MealSuggestion.model_validate(m.recipe_json),['peanuts']) for m in meals)
                    live['meals']={'seconds':round(time.monotonic()-started,1),'titles':[m.title for m in meals],'recipes_with_steps':sum(bool(m.recipe_json.get('steps')) for m in meals)}
            eng.dispose()
    except Exception as exc:
        live['failure']={'error_type':type(exc).__name__}
        if isinstance(exc, httpx.HTTPStatusError):
            live['failure']['status']=exc.response.status_code
            live['failure']['path']=exc.request.url.path
            try: live['failure']['code']=exc.response.json().get('error_code',exc.response.json().get('code'))
            except ValueError: pass
    finally:
        with httpx.Client(timeout=30) as client:
            if objects:
                result=client.request('DELETE',cfg.supabase_base+'/storage/v1/object/'+cfg.supabase_storage_bucket,headers=admin_headers,json={'prefixes':objects})
                live['storage_cleanup']=result.status_code in (200,204)
            cleanup=[]
            for user_id in users:
                response=client.delete(cfg.supabase_base+'/auth/v1/admin/users/'+user_id,headers=admin_headers)
                cleanup.append(response.status_code in (200,204))
            live['auth_cleanup']=all(cleanup)
        storage_client._client.close()
    print(json.dumps({'live_exercise':live},indent=2))
    if 'failure' in live or live.get('storage_cleanup') is False or not live.get('auth_cleanup'):
        sys.exit(1)

if '--scratch-migration' in sys.argv:
    # All DDL runs in one transaction in a unique schema; never resolve public
    # tables. Rolling back removes the schema and every synthetic row/table.
    import uuid
    from alembic import command
    from app.migrations import alembic_config
    schema='fridge_check_'+uuid.uuid4().hex
    eng=create_engine(cfg.database_url,connect_args={'connect_timeout':15})
    try:
        with eng.connect() as con:
            transaction=con.begin()
            try:
                con.execute(text(f'CREATE SCHEMA "{schema}"'))
                con.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                migration=alembic_config()
                migration.attributes['connection']=con
                command.upgrade(migration,'head')
                assert con.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0005'
                columns=con.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema=:schema AND table_name='meal_plans'"),{'schema':schema}).scalars().all()
                assert {'status','requested_count','error'} <= set(columns)
                assert con.execute(text("SELECT rowsecurity FROM pg_tables WHERE schemaname=:schema AND tablename='action_receipts'"),{'schema':schema}).scalar() is True
            finally:
                transaction.rollback()
            assert con.execute(text('SELECT count(*) FROM pg_namespace WHERE nspname=:schema'),{'schema':schema}).scalar()==0
        print(json.dumps({'scratch_migration':{'head':'0005','new_table_rls':True,'schema_rolled_back':True}}))
    except Exception as exc:
        print(json.dumps({'scratch_migration':{'ok':False,'error_type':type(exc).__name__}}))
        sys.exit(1)
    finally:
        eng.dispose()

if any(isinstance(result, dict) and (result.get('ok') is False or
       result.get('status', 200) != 200 or result.get('private') is False or
       result.get('email_enabled') is False or result.get('vision_available') is False or
       result.get('meal_available') is False) for result in results.values()):
    sys.exit(1)
