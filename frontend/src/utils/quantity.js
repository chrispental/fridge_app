// Inventory math leaves long floats (10 of 12 eggs is 0.8333… dozen); show two decimals at most.
export const formatQty = (n) => String(Number(Number(n).toFixed(2)))

// "1" means different things per unit: one bell pepper is nearly out, one jar is a full jar.
// Counted pieces and small measures are low at 1; containers and bulk units once half is gone.
const LOW_AT_ONE = new Set(['piece', 'tsp', 'tbsp', 'fl oz', 'oz', 'cup'])
export const isLowStock = (item) =>
  item.quantity != null && item.unit !== 'unknown' && item.quantity <= (LOW_AT_ONE.has(item.unit) ? 1 : 0.5)
