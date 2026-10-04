// Extra cues for common heat hazards, including saved recipes generated before
// safety guidance was added to the prompt. These are reminders, not a safety audit.
export function stepSafety(steps, index) {
  // "Hot" in a condiment name describes spice, not cooking temperature.
  const heatText = (text) => text.toLowerCase().replace(/\bhot\s+(sauce|peppers?|paprika|mustard)\b/g, '$1')
  const step = heatText(steps[index] || '')
  const prior = heatText(steps.slice(0, index).join(' '))
  const heat = /\b(hot|heat|heated|heating|preheat|fry|frying|sear|searing|sauté|saute|bake|baking|roast|roasting|broil|grill|boil|simmer)\w*\b/
  const hotContext = heat.test(step) || heat.test(prior)
  // Ordinary heating, simmering and stirring don't need an extra banner.
  // Keep one concise cue for the handling action, unless the step covers it.
  if (/\b(drain\w*|uncover\w*|(?:open|lift|remove)\w*\s+(?:the\s+)?lid)\b/.test(step) && hotContext &&
      !/\b(away from|slowly|carefully|steam can burn)\b/.test(step)) {
    return ['Watch for steam: open lids away from your face and drain hot liquid slowly.']
  }
  // A spoonful of oil for sautéing or stir-frying doesn't splash like a pan of frying oil.
  const spoonfulOfOil = /\b(tsp|teaspoons?|tbsp|tablespoons?)\s+(?:of\s+)?(?:[a-z]+\s+){0,2}oil\b/.test(step)
  const addingToHotOil = /\b(add|lower|place|drop)\w*\b/.test(step) &&
    /\boil\b/.test(step) && /\b(heat|hot|sizzl)\w*\b/.test(step) && !spoonfulOfOil
  const frying = /\b(fry|frying|fried|sear|searing)\b/.test(step.replace(/\bstir[- ]?fr\w*/g, '')) && !spoonfulOfOil
  if ((frying || addingToHotOil) &&
      !/\b(gently|carefully|splatter|splash)\w*\b/.test(step)) {
    return ['Lower food gently into hot oil to avoid splashes.']
  }
  // The handled thing must be the cookware itself, not food taken out of it.
  const handlingCookware = /\b(remove|take|lift|move|carry|transfer)\w*\b[^.;]{0,40}?\b(pan|skillet|pot|tray|baking sheet|dish|oven)\b/
  const ovenTurning = /\b(flip|turn)\w*\b/.test(step) && /\b(oven|roast|bake)\w*\b/.test(step + ' ' + prior)
  if ((handlingCookware.test(step) || ovenTurning) && hotContext &&
      !/\b(mitts?|potholders?|pot holders?|heat.resistant gloves?)\b/.test(step) &&
      !/\b(remove|take)\w*\s+(?:the\s+)?(?:pan|pot|skillet)\s+(?:from|off)\s+(?:the\s+)?heat\b/.test(step)) {
    return ['Use dry oven mitts to handle hot cookware; handles stay hot after cooking.']
  }
  return []
}
