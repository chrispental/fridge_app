// React Query hooks — the app's data layer. client.js stays the raw fetch layer;
// every component goes through these hooks so caching, optimistic updates, and
// error toasts are consistent.
import {
  MutationCache,
  QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { api } from './client.js'
import { toast } from '../components/Toast.jsx'

export function createQueryClient() {
  return new QueryClient({
    // The cache-level handler fires for every mutation, even ones with their own
    // onError — those handle rollback + toast themselves and opt out via meta.silent.
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (mutation?.meta?.silent) return
        toast.error(error.message)
      },
    }),
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 1 },
    },
  })
}

// ---------------------------------------------------------------- queries

export const useOnboardStatus = () =>
  useQuery({ queryKey: ['preferences', 'status'], queryFn: api.getOnboardStatus, retry: 1 })

export const usePreferences = () =>
  useQuery({ queryKey: ['preferences'], queryFn: api.getPreferences })

export const useInventory = () =>
  useQuery({ queryKey: ['inventory'], queryFn: api.getInventory })

export const useMeals = (status) =>
  useQuery({
    queryKey: ['meals', { status: status || '' }],
    queryFn: () => api.getMeals({ status }),
  })

const HISTORY_PAGE = 20

export const useInfiniteMeals = ({ status, q }) =>
  useInfiniteQuery({
    queryKey: ['meals', 'infinite', { status: status || '', q: q || '' }],
    queryFn: ({ pageParam }) =>
      api.getMeals({ status, q, limit: HISTORY_PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, all) =>
      last.length === HISTORY_PAGE
        ? all.reduce((n, page) => n + page.length, 0)
        : undefined,
  })

export const useDeliveryStatus = () =>
  useQuery({ queryKey: ['meals', 'delivery-status'], queryFn: api.getDeliveryStatus })

export const useMealStats = () =>
  useQuery({ queryKey: ['meals', 'stats'], queryFn: api.getMealStats })

// /plans/current 404s when no plan exists — that's "empty", not an error.
export const useCurrentPlan = () =>
  useQuery({
    queryKey: ['plans', 'current'],
    queryFn: () =>
      api.getCurrentPlan().catch((e) => {
        if (e.status === 404) return null
        throw e
      }),
    retry: false,
  })

export const usePlanShoppingList = (planId) =>
  useQuery({
    queryKey: ['plans', planId, 'shopping-list'],
    queryFn: () => api.getShoppingList(planId),
    enabled: planId != null,
  })

export const useExtraction = (batchId) =>
  useQuery({
    queryKey: ['extractions', batchId],
    queryFn: () => api.getExtraction(batchId),
    staleTime: Infinity, // review data is a fixed snapshot; the user edits it locally
  })

// ------------------------------------------------------ meal cache helpers

// Apply a partial update to a meal wherever it lives: meal lists, infinite
// history pages, and the current plan's entries. Unknown shapes pass through.
function mapMealData(data, mealId, patch) {
  if (!data) return data
  if (Array.isArray(data)) {
    return data.map((m) => (m && m.id === mealId ? { ...m, ...patch } : m))
  }
  if (Array.isArray(data.pages)) {
    return { ...data, pages: data.pages.map((p) => mapMealData(p, mealId, patch)) }
  }
  if (Array.isArray(data.entries)) {
    return {
      ...data,
      entries: data.entries.map((e) =>
        e.meal?.id === mealId ? { ...e, meal: { ...e.meal, ...patch } } : e,
      ),
    }
  }
  return data
}

function patchMealCaches(queryClient, mealId, patch) {
  const snapshots = []
  for (const rootKey of [['meals'], ['plans']]) {
    for (const [key, data] of queryClient.getQueriesData({ queryKey: rootKey })) {
      const next = mapMealData(data, mealId, patch)
      if (next !== data) {
        snapshots.push([key, data])
        queryClient.setQueryData(key, next)
      }
    }
  }
  return snapshots
}

function restoreSnapshots(queryClient, snapshots = []) {
  for (const [key, data] of snapshots) queryClient.setQueryData(key, data)
}

// A naive-UTC timestamp matching the backend's format (no trailing Z).
const utcNow = () => new Date().toISOString().replace('Z', '')

// ------------------------------------------------------------- mutations

export function useAddItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.addItem,
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey: ['inventory'] })
      const prev = queryClient.getQueryData(['inventory'])
      const temp = { id: -Date.now(), image_url: null, source: 'manual', ...body }
      queryClient.setQueryData(['inventory'], (cur) => [temp, ...(cur || [])])
      return { prev }
    },
    onError: (e, _body, ctx) => {
      queryClient.setQueryData(['inventory'], ctx.prev)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
    meta: { silent: true },
  })
}

export function useUpdateItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }) => api.updateItem(id, body),
    onMutate: async ({ id, body }) => {
      await queryClient.cancelQueries({ queryKey: ['inventory'] })
      const prev = queryClient.getQueryData(['inventory'])
      queryClient.setQueryData(['inventory'], (cur) =>
        cur?.map((it) => (it.id === id ? { ...it, ...body } : it)),
      )
      return { prev }
    },
    onError: (e, _vars, ctx) => {
      queryClient.setQueryData(['inventory'], ctx.prev)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
    meta: { silent: true },
  })
}

export function useDeleteItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.deleteItem,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['inventory'] })
      const prev = queryClient.getQueryData(['inventory'])
      queryClient.setQueryData(['inventory'], (cur) => cur?.filter((it) => it.id !== id))
      return { prev }
    },
    onError: (e, _id, ctx) => {
      queryClient.setQueryData(['inventory'], ctx.prev)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
    meta: { silent: true },
  })
}

export function useBackfillImages() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.backfillImages,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
  })
}

export function useCookMeal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, decrement }) => api.cookMeal(id, decrement),
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: ['meals'] })
      await queryClient.cancelQueries({ queryKey: ['plans'] })
      const snapshots = patchMealCaches(queryClient, id, {
        status: 'cooked',
        cooked_at: utcNow(),
      })
      return { snapshots }
    },
    onError: (e, _vars, ctx) => {
      restoreSnapshots(queryClient, ctx.snapshots)
      toast.error(e.message)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['meals'] })
      queryClient.invalidateQueries({ queryKey: ['inventory'] }) // cook may decrement
    },
    meta: { silent: true },
  })
}

export function useSubmitFeedback() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rating, tags, notes }) =>
      api.submitFeedback(id, { rating, tags, notes }),
    onMutate: async ({ id, rating, tags, notes }) => {
      await queryClient.cancelQueries({ queryKey: ['meals'] })
      const snapshots = patchMealCaches(queryClient, id, {
        rating,
        feedback_tags: tags,
        feedback_notes: notes,
      })
      return { snapshots }
    },
    onError: (e, _vars, ctx) => {
      restoreSnapshots(queryClient, ctx.snapshots)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['meals'] }),
    meta: { silent: true },
  })
}

export function useOrderDelivery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.orderDelivery,
    onSuccess: (updated) => {
      patchMealCaches(queryClient, updated.id, updated)
      queryClient.invalidateQueries({ queryKey: ['meals', 'delivery-status'] })
    },
    meta: { silent: true }, // MealCard shows the error inline next to the button
  })
}

export function useSuggestMeals() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.suggestMeals,
    onSuccess: () => {
      // Every suggestion is logged as a Meal, so history/home lists are stale now.
      queryClient.invalidateQueries({ queryKey: ['meals'] })
    },
    meta: { silent: true }, // SuggestMeal shows a rich inline error banner
  })
}

export function useCreatePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.createPlan,
    onSuccess: (plan) => {
      queryClient.setQueryData(['plans', 'current'], plan)
      queryClient.invalidateQueries({ queryKey: ['plans', plan.id, 'shopping-list'] })
      queryClient.invalidateQueries({ queryKey: ['meals'] })
    },
    meta: { silent: true },
  })
}

export function useDeletePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.deletePlan,
    onSuccess: () => {
      queryClient.setQueryData(['plans', 'current'], null)
    },
    meta: { silent: true },
  })
}

export function useSwapPlanSlot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ planId, slot }) => api.swapPlanSlot(planId, slot),
    onSuccess: (updated, { planId }) => {
      queryClient.setQueryData(['plans', 'current'], updated)
      queryClient.invalidateQueries({ queryKey: ['plans', planId, 'shopping-list'] })
      queryClient.invalidateQueries({ queryKey: ['meals'] })
    },
  })
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.updatePreferences,
    onSuccess: (updated) => {
      queryClient.setQueryData(['preferences'], updated)
      queryClient.setQueryData(['preferences', 'status'], { onboarded: true })
    },
  })
}

// ------------------------------------------------------- shopping list

export const useShoppingList = () =>
  useQuery({ queryKey: ['shopping-list'], queryFn: api.getShoppingListItems })

export function useAddShoppingItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.addShoppingItem,
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey: ['shopping-list'] })
      const prev = queryClient.getQueryData(['shopping-list'])
      const temp = { id: -Date.now(), checked: false, source: 'manual', ...body }
      queryClient.setQueryData(['shopping-list'], (cur) => [temp, ...(cur || [])])
      return { prev }
    },
    onError: (e, _body, ctx) => {
      queryClient.setQueryData(['shopping-list'], ctx.prev)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['shopping-list'] }),
    meta: { silent: true },
  })
}

export function useUpdateShoppingItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }) => api.updateShoppingItem(id, body),
    onMutate: async ({ id, body }) => {
      await queryClient.cancelQueries({ queryKey: ['shopping-list'] })
      const prev = queryClient.getQueryData(['shopping-list'])
      queryClient.setQueryData(['shopping-list'], (cur) =>
        cur?.map((it) => (it.id === id ? { ...it, ...body } : it)),
      )
      return { prev }
    },
    onError: (e, _vars, ctx) => {
      queryClient.setQueryData(['shopping-list'], ctx.prev)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['shopping-list'] }),
    meta: { silent: true },
  })
}

export function useDeleteShoppingItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.deleteShoppingItem,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['shopping-list'] })
      const prev = queryClient.getQueryData(['shopping-list'])
      queryClient.setQueryData(['shopping-list'], (cur) => cur?.filter((it) => it.id !== id))
      return { prev }
    },
    onError: (e, _id, ctx) => {
      queryClient.setQueryData(['shopping-list'], ctx.prev)
      toast.error(e.message)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['shopping-list'] }),
    meta: { silent: true },
  })
}

export function useClearChecked() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.clearChecked,
    onSuccess: (remaining) => queryClient.setQueryData(['shopping-list'], remaining),
  })
}

export function useCheckedToInventory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.checkedToInventory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shopping-list'] })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
    },
  })
}

export function useImportPlanToList() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.importPlanToList,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shopping-list'] }),
  })
}

export function useImportMealToList() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.importMealToList,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shopping-list'] }),
    meta: { silent: true }, // MealCard toasts on success; errors toast below
    onError: (e) => toast.error(e.message),
  })
}

export function useConfirmExtraction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ batchId, items }) => api.confirmExtraction(batchId, items),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
    meta: { silent: true }, // ReviewExtraction shows the error inline
  })
}
