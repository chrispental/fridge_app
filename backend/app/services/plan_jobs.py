"""Durable, resumable meal planning for the app's single Uvicorn process.

The worker uses its own sessions. Each completed slot commits with its meal;
network calls never keep an uncommitted partial slot. Restarted jobs are offered
for explicit resume instead of silently starting new billable AI requests.
"""
import logging
from threading import Event, Thread

from sqlalchemy import update

from .. import database, models
from .meal_engine import suggest_meals

logger = logging.getLogger(__name__)


def fill_plan(plan_id, sessions=None, stop=None):
    sessions = sessions or database.SessionLocal
    try:
        while not (stop and stop.is_set()):
            with sessions() as db:
                plan = db.get(models.MealPlan, plan_id)
                if plan is None or plan.status != "generating":
                    return
                existing = list(plan.entries)
                if len(existing) >= plan.requested_count:
                    plan.status, plan.error = "ready", None
                    db.commit()
                    return
                meals = suggest_meals(db, plan.user_id, count=1, commit=False,
                                      exclude_titles=[e.meal.title for e in existing])
                if not meals:
                    raise RuntimeError("No distinct meal fits the current preferences.")
                db.add(models.MealPlanEntry(plan_id=plan.id, meal_id=meals[0].id, slot_index=len(existing)))
                db.commit()
    except Exception:
        logger.exception("Plan %s paused after generation failed", plan_id)
        with sessions() as db:
            plan = db.get(models.MealPlan, plan_id)
            if plan is not None:
                plan.status = "failed"
                plan.error = "Planning paused. Completed meals are saved. Try resuming, or adjust your preferences."
                db.commit()


def start_worker():
    stop = Event()
    # Only one application process is supported by the shipped entrypoint.
    with database.SessionLocal() as db:
        db.execute(update(models.MealPlan).where(models.MealPlan.status == "generating").values(
            status="failed", error="Planning was interrupted. Resume to finish your remaining meals."))
        db.commit()

    def run():
        while not stop.is_set():
            try:
                with database.SessionLocal() as db:
                    plan = db.query(models.MealPlan).filter_by(status="queued").order_by(models.MealPlan.created_at).first()
                    if plan is not None:
                        plan_id = plan.id
                        claimed = db.execute(update(models.MealPlan).where(
                            models.MealPlan.id == plan_id, models.MealPlan.status == "queued"
                        ).values(status="generating")).rowcount
                        db.commit()
                    else:
                        claimed = False
                if claimed:
                    fill_plan(plan_id, stop=stop)
                    continue
            except Exception:
                logger.exception("Plan worker could not check the queue")
            stop.wait(1)

    thread = Thread(target=run, name="meal-planner", daemon=True)
    thread.start()
    return stop, thread
