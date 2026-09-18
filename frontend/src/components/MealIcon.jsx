import { CookingPot, Flame, Microwave, Salad, Utensils } from 'lucide-react'

export default function MealIcon({ method, size = 30 }) {
  const Icon = ({ stovetop: CookingPot, oven: Microwave, grill: Flame, 'no-cook': Salad, 'slow cooker': CookingPot })[method?.toLowerCase()] || Utensils
  return <Icon size={size} strokeWidth={1.6} aria-hidden="true" />
}
