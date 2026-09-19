// Extra cues for common heat hazards, including saved recipes generated before
// safety guidance was added to the prompt. These are reminders, not a safety audit.
export function stepSafety(steps, index) {
  // "Hot" in a condiment name describes spice, not cooking temperature.
  const heatText = (text) => text.toLowerCase().replace(/\bhot\s+(sauce|peppers?|paprika|mustard)\b/g, '$1')
  const step = heatText(steps[index] || '')
  const prior = heatText(steps.slice(0, index).join(' '))
  const heat = /\b(hot|heat|heated|heating|preheat|fry|frying|sear|searing|sauté|saute|bake|baking|roast|roasting|broil|grill|boil|simmer)\w*\b/
  const cookware = /\b(pan|skillet|pot|tray|baking sheet|dish|handle|oven|grill)\b/
  const hotContext = heat.test(step) || heat.test(prior)
  // Ordinary heating, simmering and stirring don't need an extra banner.
  // Keep one concise cue for the handling action, unless the step covers it.
  if (/\b(drain\w*|uncover\w*|(?:open|lift|remove)\w*\s+(?:the\s+)?lid)\b/.test(step) && hotContext &&
      !/\b(away from|slowly|carefully|steam can burn)\b/.test(step)) {
    return ['Watch for steam: open lids away from your face and drain hot liquid slowly.']
  }
  const addingToHotOil = /\b(add|lower|place|drop)\w*\b/.test(step) &&
    /\boil\b/.test(step) && /\b(heat|hot|sizzl)\w*\b/.test(step)
  if ((/\b(fry|frying|sauté|saute|sear|searing)\w*\b/.test(step) || addingToHotOil) &&
      !/\b(gently|carefully|splatter|splash)\w*\b/.test(step)) {
    return ['Lower food gently into hot oil to avoid splashes.']
  }
  const handling = /\b(remove|take|lift|move|carry|transfer)\w*\b/
  const ovenTurning = /\b(flip|turn)\w*\b/.test(step) && /\b(oven|roast|bake)\w*\b/.test(step + ' ' + prior)
  if (((handling.test(step) && cookware.test(step)) || ovenTurning) && hotContext &&
      !/\b(mitts?|potholders?|pot holders?|heat.resistant gloves?)\b/.test(step) &&
      !/\b(remove|take)\w*\s+(?:the\s+)?(?:pan|pot|skillet)\s+(?:from|off)\s+(?:the\s+)?heat\b/.test(step)) {
    return ['Use dry oven mitts to handle hot cookware; handles stay hot after cooking.']
  }
  return []
}
