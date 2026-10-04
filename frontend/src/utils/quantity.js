// Inventory math leaves long floats (10 of 12 eggs is 0.8333… dozen); show two decimals at most.
export const formatQty = (n) => String(Number(Number(n).toFixed(2)))
