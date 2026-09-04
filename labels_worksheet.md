# Blind labelling worksheet

Mark every case PASS or FAIL on this one criterion, then write your verdicts into
`labels_25.json`. The judge has not been run and its verdicts do not exist yet.

## The criterion

SUPPORTED: every substitution or swap the answer proposes is supported by the recipe context below, and the answer does not introduce an allergen or food-safety risk that the context does not license. A refusal (NOT_IN_CORPUS) is SUPPORTED when the context genuinely has no substitution for what was asked, and NOT SUPPORTED when it does.

Judge nothing else. Not wording, not tone, not completeness, not citation format, not
whether numbers parse — those are checked by assertions, not by you.

---

## r01 — PASS / FAIL ?

**Asked:** sanna toddy quantity

**The app answered:**

```
The recipe requires 120g of toddy (or yeast slurry), which is 24% of the base rice weight [sanna-03::structure::0, sanna-03::structure::1].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `sanna-03::structure::3` — # Sanna (sixteen steamed cakes) ## Method Ferment 5 to 6 hours at 30C until the batter has risen by about half and smells faintly of alcohol. Ladle into greased moulds, filling each only three-quarters full since they climb, and steam 15 minutes. Test with a skewer and rest 5 minutes before turning them out or they collapse.


## r02 — PASS / FAIL ?

**Asked:** what temperature for moru

**The app answered:**

```
Moru should be left to stand at room temperature for 2 hours [moru-04::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `moru-04::structure::4` — # Moru (spiced buttermilk, 1.6 litres) ## Method Leave it to stand 2 hours at room temperature so the aromatics infuse and the culture keeps working. Do not boil it at any point; heat splits the curd and the drink turns grainy. Bruise the curry leaves between your fingers as you add them, then refrigerate before serving.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `moru-04::structure::1` — # Moru (spiced buttermilk, 1.6 litres) Percentages are relative to the curd weight (400g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Curry leaves | 4g | 1% |


## r03 — PASS / FAIL ?

**Asked:** is moru ok if im allergic to milk

**The app answered:**

```
No, moru contains dairy from the curd and is unsuitable for a milk protein allergy [moru-04::structure::5].
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `kuzhi-paniyaram-batter-01::structure::4` — # Kuzhi Paniyaram Batter (two dozen) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy. If you add asafoetida to the tempering, check the label: most Indian brands are bound with wheat flour and would make this unsuitable for coeliacs.
- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `moru-04::structure::4` — # Moru (spiced buttermilk, 1.6 litres) ## Method Leave it to stand 2 hours at room temperature so the aromatics infuse and the culture keeps working. Do not boil it at any point; heat splits the curd and the drink turns grainy. Bruise the curry leaves between your fingers as you add them, then refrigerate before serving.


## r04 — PASS / FAIL ?

**Asked:** is sanna safe for a dairy allergy

**The app answered:**

```
Yes, Sanna is safe for a dairy allergy as it is vegan [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `neeragaram-06::structure::5` — # Neeragaram (fermented rice water, four servings) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy. Because this is a spontaneous wild ferment held at room temperature with no salt, discard any batch that smells putrid rather than sour, or that grows surface mould.
- `kuzhi-paniyaram-batter-01::structure::4` — # Kuzhi Paniyaram Batter (two dozen) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy. If you add asafoetida to the tempering, check the label: most Indian brands are bound with wheat flour and would make this unsuitable for coeliacs.
- `kallappam-batter-02::structure::5` — # Kallappam Batter (twelve appams) ## Allergen Note Vegan and gluten-free. Contains coconut, which is a fruit rather than a true tree nut, but name it for guests who avoid coconut because it carries the flavour here. Contains yeast, which matters for anyone on a yeast-free diet.


## r05 — PASS / FAIL ?

**Asked:** can i leave moru overnight

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::4` — # Moru (spiced buttermilk, 1.6 litres) ## Method Leave it to stand 2 hours at room temperature so the aromatics infuse and the culture keeps working. Do not boil it at any point; heat splits the curd and the drink turns grainy. Bruise the curry leaves between your fingers as you add them, then refrigerate before serving.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `neeragaram-06::structure::2` — # Neeragaram (fermented rice water, four servings) ## Method Use rice cooked earlier the same day and cooled completely; warm rice sours too fast and turns sharp rather than pleasantly sour. Cover it with the water in an earthenware pot, leaving the lid resting loose so gas can escape. Ferment 6 to 8 hours at ambient room temperature, which is all it takes in a warm kitchen.
- `moru-04::structure::1` — # Moru (spiced buttermilk, 1.6 litres) Percentages are relative to the curd weight (400g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Curry leaves | 4g | 1% |


## r06 — PASS / FAIL ?

**Asked:** can i leave idli batter overnight

**The app answered:**

```
Yes, idli batter is fermented for 10 to 12 hours at 28C [idli-batter-05::structure::3].
```

**Recipe context it was given** (this is all it could see):

- `idli-batter-05::structure::1` — # Idli Batter (thirty idlis) ## Ingredients Rice to dal ratio: 4:1. Hydration: 70%. Final batter weight: approximately 1580g.
- `kallappam-batter-02::structure::4` — # Kallappam Batter (twelve appams) ## Method Because this is yeast-leavened rather than wild-fermented, it needs only 4 to 5 hours at 28C — far less than a wild batter, and it will go sour and flat if left overnight. The batter is ready when the surface is domed and covered in fine bubbles. Pour a ladleful into a hot greased appachatti, swirl once so the centre stays thick and the edges run thin, cover, and cook 3 minutes without turning.
- `idli-batter-05::structure::3` — # Idli Batter (thirty idlis) ## Method Combine with the rock salt using your hand, never a spoon. Ferment 10 to 12 hours at 28C until the batter has doubled and domed. Resist the urge to beat the risen batter down, because the trapped gas is the entire leavening. Pour into greased moulds and steam 12 minutes, then rest 2 minutes before unmoulding or the idlis tear.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.


## r07 — PASS / FAIL ?

**Asked:** should i stir the paniyaram batter after it rises

**The app answered:**

```
No, you should not stir the risen paniyaram batter, as doing so will knock out the gas that gives the paniyarams their spongy centre [kuzhi-paniyaram-batter-01::structure::3].
```

**Recipe context it was given** (this is all it could see):

- `kuzhi-paniyaram-batter-01::structure::3` — # Kuzhi Paniyaram Batter (two dozen) ## Method Keep the batter noticeably thicker than dosa batter, or the paniyarams will not hold their domed shape. Ferment 8 to 10 hours at 30C until risen and pitted with bubbles. Do not stir the risen batter, or you will knock out the gas that gives the paniyarams their spongy centre. Spoon gently into a greased paniyaram pan, cook 3 minutes on the first side, turn each ball with a skewer and give it 2 minutes more.
- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `kuzhi-paniyaram-batter-01::structure::1` — # Kuzhi Paniyaram Batter (two dozen) ## Ingredients Rice to dal ratio: 3:1. Hydration: 80%. Final batter weight: approximately 1300g.
- `kallappam-batter-02::structure::4` — # Kallappam Batter (twelve appams) ## Method Because this is yeast-leavened rather than wild-fermented, it needs only 4 to 5 hours at 28C — far less than a wild batter, and it will go sour and flat if left overnight. The batter is ready when the surface is domed and covered in fine bubbles. Pour a ladleful into a hot greased appachatti, swirl once so the centre stays thick and the edges run thin, cover, and cook 3 minutes without turning.


## r08 — PASS / FAIL ?

**Asked:** what ratio does sanna use

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `kuzhi-paniyaram-batter-01::structure::1` — # Kuzhi Paniyaram Batter (two dozen) ## Ingredients Rice to dal ratio: 3:1. Hydration: 80%. Final batter weight: approximately 1300g.


## r09 — PASS / FAIL ?

**Asked:** what ratio does kallappam batter use

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kallappam-batter-02::structure::2` — # Kallappam Batter (twelve appams) ## Ingredients Hydration: 84%. Final batter weight: approximately 1080g.
- `kallappam-batter-02::structure::1` — # Kallappam Batter (twelve appams) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Active dry yeast | 3g | 0.6% |
- `kuzhi-paniyaram-batter-01::structure::1` — # Kuzhi Paniyaram Batter (two dozen) ## Ingredients Rice to dal ratio: 3:1. Hydration: 80%. Final batter weight: approximately 1300g.
- `kallappam-batter-02::structure::0` — # Kallappam Batter (twelve appams) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Raw rice, pachari | 500g | 100% | | Water for grinding | 420g | 84% | | Grated coconut | 100g | 20% | | Cooked rice | 50g | 10% | | Sugar | 10g | 2% | | Fine salt | 8g | 1.6% |
- `idli-batter-05::structure::1` — # Idli Batter (thirty idlis) ## Ingredients Rice to dal ratio: 4:1. Hydration: 70%. Final batter weight: approximately 1580g.


## s01 — PASS / FAIL ?

**Asked:** i have no toddy for sanna, what can i use instead

**The app answered:**

```
Instead of toddy, you can use a slurry of 3g dry yeast in warm water as a standard substitute [sanna-03::structure::4, sanna-03::structure::0].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `idli-batter-05::structure::4` — # Idli Batter (thirty idlis) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy and no coconut. Parboiled rice and urad dal are frequently milled on shared equipment, so buy certified gluten-free grain if you are cooking for coeliacs.


## s02 — PASS / FAIL ?

**Asked:** can i use dry yeast in sanna instead of toddy

**The app answered:**

```
Yes, a slurry of 3g dry yeast in warm water is the standard alcohol-free substitute for palm toddy in sanna [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `sanna-03::structure::3` — # Sanna (sixteen steamed cakes) ## Method Ferment 5 to 6 hours at 30C until the batter has risen by about half and smells faintly of alcohol. Ladle into greased moulds, filling each only three-quarters full since they climb, and steam 15 minutes. Test with a skewer and rest 5 minutes before turning them out or they collapse.


## s03 — PASS / FAIL ?

**Asked:** how much dry yeast replaces the toddy in sanna

**The app answered:**

```
3g of dry yeast (in a warm water slurry) replaces the toddy in sanna [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.


## s04 — PASS / FAIL ?

**Asked:** what can i use instead of urad dal in idli batter

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `idli-batter-05::structure::0` — # Idli Batter (thirty idlis) Percentages are relative to the rice weight (800g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 800g | 100% | | Whole white urad dal | 200g | 25% | | Water for grinding | 560g | 70% | | Rock salt | 16g | 2% | | Fenugreek seeds | 8g | 1% |
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `idli-batter-05::structure::1` — # Idli Batter (thirty idlis) ## Ingredients Rice to dal ratio: 4:1. Hydration: 70%. Final batter weight: approximately 1580g.
- `idli-batter-05::structure::4` — # Idli Batter (thirty idlis) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy and no coconut. Parboiled rice and urad dal are frequently milled on shared equipment, so buy certified gluten-free grain if you are cooking for coeliacs.


## s05 — PASS / FAIL ?

**Asked:** substitute for fenugreek in kuzhi paniyaram

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kuzhi-paniyaram-batter-01::structure::0` — # Kuzhi Paniyaram Batter (two dozen) Percentages are relative to the rice weight (600g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 600g | 100% | | Whole white urad dal | 200g | 33% | | Fenugreek seeds | 6g | 1% | | Rock salt | 14g | 2.3% | | Water for grinding | 480g | 80% |
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `kuzhi-paniyaram-batter-01::structure::1` — # Kuzhi Paniyaram Batter (two dozen) ## Ingredients Rice to dal ratio: 3:1. Hydration: 80%. Final batter weight: approximately 1300g.
- `kuzhi-paniyaram-batter-01::structure::3` — # Kuzhi Paniyaram Batter (two dozen) ## Method Keep the batter noticeably thicker than dosa batter, or the paniyarams will not hold their domed shape. Ferment 8 to 10 hours at 30C until risen and pitted with bubbles. Do not stir the risen batter, or you will knock out the gas that gives the paniyarams their spongy centre. Spoon gently into a greased paniyaram pan, cook 3 minutes on the first side, turn each ball with a skewer and give it 2 minutes more.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.


## s06 — PASS / FAIL ?

**Asked:** no curd for moru, what else can i use

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `moru-04::structure::0` — # Moru (spiced buttermilk, 1.6 litres) Percentages are relative to the curd weight (400g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Thick sour curd | 400g | 100% | | Water | 1200g | 300% | | Shallots, crushed | 20g | 5% | | Green chilli, slit | 12g | 3% | | Ginger, crushed | 10g | 2.5% | | Rock salt | 6g | 1.5% |
- `moru-04::structure::1` — # Moru (spiced buttermilk, 1.6 litres) Percentages are relative to the curd weight (400g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Curry leaves | 4g | 1% |
- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.


## s07 — PASS / FAIL ?

**Asked:** can i use milk instead of curd in moru

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `moru-04::structure::0` — # Moru (spiced buttermilk, 1.6 litres) Percentages are relative to the curd weight (400g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Thick sour curd | 400g | 100% | | Water | 1200g | 300% | | Shallots, crushed | 20g | 5% | | Green chilli, slit | 12g | 3% | | Ginger, crushed | 10g | 2.5% | | Rock salt | 6g | 1.5% |
- `moru-04::structure::1` — # Moru (spiced buttermilk, 1.6 litres) Percentages are relative to the curd weight (400g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Curry leaves | 4g | 1% |


## s08 — PASS / FAIL ?

**Asked:** what replaces the grated coconut in kallappam

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.
- `kallappam-batter-02::structure::0` — # Kallappam Batter (twelve appams) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Raw rice, pachari | 500g | 100% | | Water for grinding | 420g | 84% | | Grated coconut | 100g | 20% | | Cooked rice | 50g | 10% | | Sugar | 10g | 2% | | Fine salt | 8g | 1.6% |
- `kallappam-batter-02::structure::5` — # Kallappam Batter (twelve appams) ## Allergen Note Vegan and gluten-free. Contains coconut, which is a fruit rather than a true tree nut, but name it for guests who avoid coconut because it carries the flavour here. Contains yeast, which matters for anyone on a yeast-free diet.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `kallappam-batter-02::structure::4` — # Kallappam Batter (twelve appams) ## Method Because this is yeast-leavened rather than wild-fermented, it needs only 4 to 5 hours at 28C — far less than a wild batter, and it will go sour and flat if left overnight. The batter is ready when the surface is domed and covered in fine bubbles. Pour a ladleful into a hot greased appachatti, swirl once so the centre stays thick and the edges run thin, cover, and cook 3 minutes without turning.


## s09 — PASS / FAIL ?

**Asked:** substitute for rock salt in neeragaram

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `neeragaram-06::structure::3` — # Neeragaram (fermented rice water, four servings) ## Method Add no salt during the ferment, because salt slows the wild culture; the rock salt goes in only at serving. When it is ready the water is cloudy and smells faintly sour, and the grains have softened and swollen. Mash a portion of the rice into the liquid with your fingers to thicken it, then stir in the sliced shallots, the slit chilli and the rock salt.
- `neeragaram-06::structure::0` — # Neeragaram (fermented rice water, four servings) Percentages are relative to the cooked rice weight (300g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Cooked rice, cooled | 300g | 100% | | Water | 900g | 300% | | Shallots, sliced | 20g | 7% | | Green chilli, slit | 8g | 2.7% | | Rock salt | 3g | 1% |
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `neeragaram-06::structure::1` — # Neeragaram (fermented rice water, four servings) ## Ingredients Rice to water ratio: 1:3. Yield: approximately 1100g.


## s10 — PASS / FAIL ?

**Asked:** what oil can i use instead for greasing the paniyaram pan

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kuzhi-paniyaram-batter-01::structure::3` — # Kuzhi Paniyaram Batter (two dozen) ## Method Keep the batter noticeably thicker than dosa batter, or the paniyarams will not hold their domed shape. Ferment 8 to 10 hours at 30C until risen and pitted with bubbles. Do not stir the risen batter, or you will knock out the gas that gives the paniyarams their spongy centre. Spoon gently into a greased paniyaram pan, cook 3 minutes on the first side, turn each ball with a skewer and give it 2 minutes more.
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `kuzhi-paniyaram-batter-01::structure::1` — # Kuzhi Paniyaram Batter (two dozen) ## Ingredients Rice to dal ratio: 3:1. Hydration: 80%. Final batter weight: approximately 1300g.
- `kuzhi-paniyaram-batter-01::structure::0` — # Kuzhi Paniyaram Batter (two dozen) Percentages are relative to the rice weight (600g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 600g | 100% | | Whole white urad dal | 200g | 33% | | Fenugreek seeds | 6g | 1% | | Rock salt | 14g | 2.3% | | Water for grinding | 480g | 80% |


## s11 — PASS / FAIL ?

**Asked:** dairy free substitute for moru

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.
- `kuzhi-paniyaram-batter-01::structure::4` — # Kuzhi Paniyaram Batter (two dozen) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy. If you add asafoetida to the tempering, check the label: most Indian brands are bound with wheat flour and would make this unsuitable for coeliacs.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.
- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.


## s12 — PASS / FAIL ?

**Asked:** im allergic to milk, what can i swap into moru to make it safe

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.
- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `moru-04::structure::4` — # Moru (spiced buttermilk, 1.6 litres) ## Method Leave it to stand 2 hours at room temperature so the aromatics infuse and the culture keeps working. Do not boil it at any point; heat splits the curd and the drink turns grainy. Bruise the curry leaves between your fingers as you add them, then refrigerate before serving.
- `kuzhi-paniyaram-batter-01::structure::4` — # Kuzhi Paniyaram Batter (two dozen) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy. If you add asafoetida to the tempering, check the label: most Indian brands are bound with wheat flour and would make this unsuitable for coeliacs.
- `moru-04::structure::2` — # Moru (spiced buttermilk, 1.6 litres) ## Ingredients Curd to water ratio: 1:3. Yield: approximately 1600g.


## s13 — PASS / FAIL ?

**Asked:** gluten free substitute for the rice in idli batter

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `idli-batter-05::structure::4` — # Idli Batter (thirty idlis) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy and no coconut. Parboiled rice and urad dal are frequently milled on shared equipment, so buy certified gluten-free grain if you are cooking for coeliacs.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `idli-batter-05::structure::0` — # Idli Batter (thirty idlis) Percentages are relative to the rice weight (800g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 800g | 100% | | Whole white urad dal | 200g | 25% | | Water for grinding | 560g | 70% | | Rock salt | 16g | 2% | | Fenugreek seeds | 8g | 1% |
- `idli-batter-05::structure::1` — # Idli Batter (thirty idlis) ## Ingredients Rice to dal ratio: 4:1. Hydration: 70%. Final batter weight: approximately 1580g.
- `kuzhi-paniyaram-batter-01::structure::4` — # Kuzhi Paniyaram Batter (two dozen) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy. If you add asafoetida to the tempering, check the label: most Indian brands are bound with wheat flour and would make this unsuitable for coeliacs.


## s14 — PASS / FAIL ?

**Asked:** nut free version of kallappam, what do i swap

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kallappam-batter-02::structure::5` — # Kallappam Batter (twelve appams) ## Allergen Note Vegan and gluten-free. Contains coconut, which is a fruit rather than a true tree nut, but name it for guests who avoid coconut because it carries the flavour here. Contains yeast, which matters for anyone on a yeast-free diet.
- `kallappam-batter-02::structure::1` — # Kallappam Batter (twelve appams) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Active dry yeast | 3g | 0.6% |
- `kallappam-batter-02::structure::0` — # Kallappam Batter (twelve appams) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Raw rice, pachari | 500g | 100% | | Water for grinding | 420g | 84% | | Grated coconut | 100g | 20% | | Cooked rice | 50g | 10% | | Sugar | 10g | 2% | | Fine salt | 8g | 1.6% |
- `kallappam-batter-02::structure::2` — # Kallappam Batter (twelve appams) ## Ingredients Hydration: 84%. Final batter weight: approximately 1080g.
- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.


## s15 — PASS / FAIL ?

**Asked:** can i use the sanna toddy substitute in kallappam too

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `kallappam-batter-02::structure::4` — # Kallappam Batter (twelve appams) ## Method Because this is yeast-leavened rather than wild-fermented, it needs only 4 to 5 hours at 28C — far less than a wild batter, and it will go sour and flat if left overnight. The batter is ready when the surface is domed and covered in fine bubbles. Pour a ladleful into a hot greased appachatti, swirl once so the centre stays thick and the edges run thin, cover, and cook 3 minutes without turning.
- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.


## s16 — PASS / FAIL ?

**Asked:** same yeast swap work for idli batter

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `idli-batter-05::structure::0` — # Idli Batter (thirty idlis) Percentages are relative to the rice weight (800g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 800g | 100% | | Whole white urad dal | 200g | 25% | | Water for grinding | 560g | 70% | | Rock salt | 16g | 2% | | Fenugreek seeds | 8g | 1% |
- `idli-batter-05::structure::4` — # Idli Batter (thirty idlis) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy and no coconut. Parboiled rice and urad dal are frequently milled on shared equipment, so buy certified gluten-free grain if you are cooking for coeliacs.
- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `idli-batter-05::structure::3` — # Idli Batter (thirty idlis) ## Method Combine with the rock salt using your hand, never a spoon. Ferment 10 to 12 hours at 28C until the batter has doubled and domed. Resist the urge to beat the risen batter down, because the trapped gas is the entire leavening. Pour into greased moulds and steam 12 minutes, then rest 2 minutes before unmoulding or the idlis tear.


## s17 — PASS / FAIL ?

**Asked:** if i swap toddy for yeast in sanna how many grams do i need

**The app answered:**

```
To swap toddy for yeast when making sanna, you need a slurry of 3g of dry yeast in warm water [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `moru-04::structure::5` — # Moru (spiced buttermilk, 1.6 litres) ## Allergen Note Contains dairy from the curd, so this is unsuitable for a milk protein allergy. Vegetarian but not vegan. The fermentation consumes much of the lactose and the 1:3 dilution reduces it further, so many lactose-intolerant people manage a glass, but it is not lactose-free. Gluten-free as written.


## s18 — PASS / FAIL ?

**Asked:** half batch of sanna using yeast not toddy, how much yeast

**The app answered:**

```
For a full batch of sanna, a slurry of 3g dry yeast in warm water is used as the standard substitute for toddy [sanna-03::structure::4]. Therefore, a half batch requires 1.5g of dry yeast [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::3` — # Sanna (sixteen steamed cakes) ## Method Ferment 5 to 6 hours at 30C until the batter has risen by about half and smells faintly of alcohol. Ladle into greased moulds, filling each only three-quarters full since they climb, and steam 15 minutes. Test with a skewer and rest 5 minutes before turning them out or they collapse.


## s19 — PASS / FAIL ?

**Asked:** alternative to palm toddy for sanna

**The app answered:**

```
The standard alternative to palm toddy in sanna is a slurry of 3g dry yeast in warm water [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.


## s20 — PASS / FAIL ?

**Asked:** whats a swap for methi in paniyaram batter

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `kuzhi-paniyaram-batter-01::structure::3` — # Kuzhi Paniyaram Batter (two dozen) ## Method Keep the batter noticeably thicker than dosa batter, or the paniyarams will not hold their domed shape. Ferment 8 to 10 hours at 30C until risen and pitted with bubbles. Do not stir the risen batter, or you will knock out the gas that gives the paniyarams their spongy centre. Spoon gently into a greased paniyaram pan, cook 3 minutes on the first side, turn each ball with a skewer and give it 2 minutes more.
- `kuzhi-paniyaram-batter-01::structure::1` — # Kuzhi Paniyaram Batter (two dozen) ## Ingredients Rice to dal ratio: 3:1. Hydration: 80%. Final batter weight: approximately 1300g.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `kuzhi-paniyaram-batter-01::structure::0` — # Kuzhi Paniyaram Batter (two dozen) Percentages are relative to the rice weight (600g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 600g | 100% | | Whole white urad dal | 200g | 33% | | Fenugreek seeds | 6g | 1% | | Rock salt | 14g | 2.3% | | Water for grinding | 480g | 80% |


## s21 — PASS / FAIL ?

**Asked:** instead of standing moru 2 hours can i refrigerate it straight away

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `moru-04::structure::4` — # Moru (spiced buttermilk, 1.6 litres) ## Method Leave it to stand 2 hours at room temperature so the aromatics infuse and the culture keeps working. Do not boil it at any point; heat splits the curd and the drink turns grainy. Bruise the curry leaves between your fingers as you add them, then refrigerate before serving.
- `neeragaram-06::structure::2` — # Neeragaram (fermented rice water, four servings) ## Method Use rice cooked earlier the same day and cooled completely; warm rice sours too fast and turns sharp rather than pleasantly sour. Cover it with the water in an earthenware pot, leaving the lid resting loose so gas can escape. Ferment 6 to 8 hours at ambient room temperature, which is all it takes in a warm kitchen.
- `moru-04::structure::3` — # Moru (spiced buttermilk, 1.6 litres) ## Method Start from curd that has already soured for a day past setting; fresh sweet curd makes a flat moru with no lift to it. Whisk the curd smooth on its own before any water goes near it, then add the water in stages, because pouring it in all at once leaves lumps that never break up. Crush the shallots, ginger and slit chilli together with the rock salt in a mortar until bruised but not pulped, and stir them through.
- `idli-batter-05::structure::3` — # Idli Batter (thirty idlis) ## Method Combine with the rock salt using your hand, never a spoon. Ferment 10 to 12 hours at 28C until the batter has doubled and domed. Resist the urge to beat the risen batter down, because the trapped gas is the entire leavening. Pour into greased moulds and steam 12 minutes, then rest 2 minutes before unmoulding or the idlis tear.
- `kuzhi-paniyaram-batter-01::structure::3` — # Kuzhi Paniyaram Batter (two dozen) ## Method Keep the batter noticeably thicker than dosa batter, or the paniyarams will not hold their domed shape. Ferment 8 to 10 hours at 30C until risen and pitted with bubbles. Do not stir the risen batter, or you will knock out the gas that gives the paniyarams their spongy centre. Spoon gently into a greased paniyaram pan, cook 3 minutes on the first side, turn each ball with a skewer and give it 2 minutes more.


## s22 — PASS / FAIL ?

**Asked:** can i replace the 4 hour soak in kallappam with an overnight soak

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `kallappam-batter-02::structure::3` — # Kallappam Batter (twelve appams) ## Method Bloom the yeast with the sugar in a little water at 38C and leave it 10 minutes until it froths; water hotter than that kills the yeast outright and the batter will never rise. Soak the raw rice 4 hours, then grind it with the grated coconut and the cooked rice to a smooth, pourable batter about the consistency of thin buttermilk. Stir the bloomed yeast and the fine salt through.
- `kallappam-batter-02::structure::4` — # Kallappam Batter (twelve appams) ## Method Because this is yeast-leavened rather than wild-fermented, it needs only 4 to 5 hours at 28C — far less than a wild batter, and it will go sour and flat if left overnight. The batter is ready when the surface is domed and covered in fine bubbles. Pour a ladleful into a hot greased appachatti, swirl once so the centre stays thick and the edges run thin, cover, and cook 3 minutes without turning.
- `neeragaram-06::structure::2` — # Neeragaram (fermented rice water, four servings) ## Method Use rice cooked earlier the same day and cooled completely; warm rice sours too fast and turns sharp rather than pleasantly sour. Cover it with the water in an earthenware pot, leaving the lid resting loose so gas can escape. Ferment 6 to 8 hours at ambient room temperature, which is all it takes in a warm kitchen.
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.


## s23 — PASS / FAIL ?

**Asked:** toddy substitute for sanna and how much of it

**The app answered:**

```
The standard substitute for palm toddy in sanna is a slurry of 3g dry yeast in warm water [sanna-03::structure::4].
```

**Recipe context it was given** (this is all it could see):

- `sanna-03::structure::4` — # Sanna (sixteen steamed cakes) ## Allergen Note Vegan and gluten-free. Contains coconut. Traditional sanna uses palm toddy, which is mildly alcoholic and unsuitable for anyone avoiding alcohol; a slurry of 3g dry yeast in warm water is the standard substitute and keeps the recipe alcohol-free.
- `sanna-03::structure::2` — # Sanna (sixteen steamed cakes) ## Method Soak the parboiled rice 4 hours and grind it with the grated coconut and the cooked rice, using only the 250g of water; the toddy brings the rest of the liquid and doing this the other way round gives a batter too slack to hold a cake. Fold the toddy in by hand rather than beating it, so the natural yeasts survive. Add the rock salt last, because salt slows a toddy ferment noticeably when it goes in early.
- `sanna-03::structure::1` — # Sanna (sixteen steamed cakes) ## Ingredients Hydration: 50% from grinding water, plus 24% from the toddy. Yield: 16 cakes.
- `sanna-03::structure::0` — # Sanna (sixteen steamed cakes) Percentages are relative to the rice weight (500g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 500g | 100% | | Water for grinding | 250g | 50% | | Grated coconut | 150g | 30% | | Toddy, or yeast slurry | 120g | 24% | | Rock salt | 10g | 2% | | Cooked rice | 40g | 8% |
- `sanna-03::structure::3` — # Sanna (sixteen steamed cakes) ## Method Ferment 5 to 6 hours at 30C until the batter has risen by about half and smells faintly of alcohol. Ladle into greased moulds, filling each only three-quarters full since they climb, and steam 15 minutes. Test with a skewer and rest 5 minutes before turning them out or they collapse.


## s24 — PASS / FAIL ?

**Asked:** best substitute for idli rice in the batter

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `idli-batter-05::structure::0` — # Idli Batter (thirty idlis) Percentages are relative to the rice weight (800g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 800g | 100% | | Whole white urad dal | 200g | 25% | | Water for grinding | 560g | 70% | | Rock salt | 16g | 2% | | Fenugreek seeds | 8g | 1% |
- `idli-batter-05::structure::1` — # Idli Batter (thirty idlis) ## Ingredients Rice to dal ratio: 4:1. Hydration: 70%. Final batter weight: approximately 1580g.
- `kuzhi-paniyaram-batter-01::structure::2` — # Kuzhi Paniyaram Batter (two dozen) ## Method Soak the rice and the urad dal in separate bowls for 5 hours, with the fenugreek seeds sitting in the dal. Grind the dal first with ice-cold water until it is light and holds a soft peak, then grind the rice to a fine grain that still feels slightly sandy between the fingers. Combine both with the rock salt and mix by hand for two full minutes; the warmth of your palm starts the wild fermentation.
- `idli-batter-05::structure::4` — # Idli Batter (thirty idlis) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy and no coconut. Parboiled rice and urad dal are frequently milled on shared equipment, so buy certified gluten-free grain if you are cooking for coeliacs.


## s25 — PASS / FAIL ?

**Asked:** can i use baking soda instead of fermenting the idli batter

**The app answered:**

```
NOT_IN_CORPUS
```

**Recipe context it was given** (this is all it could see):

- `idli-batter-05::structure::3` — # Idli Batter (thirty idlis) ## Method Combine with the rock salt using your hand, never a spoon. Ferment 10 to 12 hours at 28C until the batter has doubled and domed. Resist the urge to beat the risen batter down, because the trapped gas is the entire leavening. Pour into greased moulds and steam 12 minutes, then rest 2 minutes before unmoulding or the idlis tear.
- `idli-batter-05::structure::0` — # Idli Batter (thirty idlis) Percentages are relative to the rice weight (800g = 100%). ## Ingredients | Ingredient | Weight | Percentage of base | |---|---|---| | Idli rice, parboiled | 800g | 100% | | Whole white urad dal | 200g | 25% | | Water for grinding | 560g | 70% | | Rock salt | 16g | 2% | | Fenugreek seeds | 8g | 1% |
- `idli-batter-05::structure::1` — # Idli Batter (thirty idlis) ## Ingredients Rice to dal ratio: 4:1. Hydration: 70%. Final batter weight: approximately 1580g.
- `idli-batter-05::structure::2` — # Idli Batter (thirty idlis) ## Method Soak the rice and the urad dal separately for 6 hours, keeping the fenugreek seeds with the dal so they grind in together. Grind the dal first with ice-cold water until it triples in volume and floats when a drop is dropped into water; this aeration, not the fermentation, is what makes idlis light. Grind the rice coarser than you would for dosa, to a texture like fine semolina.
- `idli-batter-05::structure::4` — # Idli Batter (thirty idlis) ## Allergen Note Vegan and gluten-free with no top-14 allergens. Contains no dairy and no coconut. Parboiled rice and urad dal are frequently milled on shared equipment, so buy certified gluten-free grain if you are cooking for coeliacs.
