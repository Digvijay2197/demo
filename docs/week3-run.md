(intermediate dump written by eval_week3_chunking.py; see week3-results.md for the real write-up)

baseline_hits=6/8 structure_hits=8/8

{'id': 'q01', 'question': 'How much fine sea salt does the 2kg sourdough recipe use?', 'recipe_id': 'sourdough-2kg', 'section': 'ingredients', 'keyword': '7 g', 'baseline_hit': True, 'baseline_top1': ('sourdough-2kg', 0.615), 'structure_hit': True, 'structure_top1': ('sourdough-2kg', 0.597, 'ingredients')}

{'id': 'q02', 'question': 'What is the hydration percentage of the 2kg sourdough recipe?', 'recipe_id': 'sourdough-2kg', 'section': 'ingredients', 'keyword': '75%', 'baseline_hit': True, 'baseline_top1': ('sourdough-2kg', 0.566), 'structure_hit': True, 'structure_top1': ('sourdough-2kg', 0.563, 'ingredients')}

{'id': 'q03', 'question': 'What is the weight of coarse sea salt used in the kimchi recipe?', 'recipe_id': 'kimchi-napa', 'section': 'ingredients', 'keyword': '50 g', 'baseline_hit': True, 'baseline_top1': ('kimchi-napa', 0.565), 'structure_hit': True, 'structure_top1': ('kimchi-napa', 0.564, 'ingredients')}

{'id': 'q04', 'question': 'How much white sugar is used to brew the kombucha?', 'recipe_id': 'kombucha-ginger', 'section': 'ingredients', 'keyword': '100 g', 'baseline_hit': True, 'baseline_top1': ('kombucha-ginger', 0.631), 'structure_hit': True, 'structure_top1': ('kombucha-ginger', 0.66, 'method')}

{'id': 'q05', 'question': 'What temperature should the milk be heated to when making homemade yogurt?', 'recipe_id': 'yogurt-dairy', 'section': 'method', 'keyword': '85 C', 'baseline_hit': False, 'baseline_top1': ('yogurt-dairy', 0.597), 'structure_hit': True, 'structure_top1': ('yogurt-dairy', 0.721, 'method')}

{'id': 'q06', 'question': 'How long should the homemade miso ferment before it is ready?', 'recipe_id': 'miso-soybean', 'section': 'method', 'keyword': '6 to 12 months', 'baseline_hit': False, 'baseline_top1': ('miso-soybean', 0.528), 'structure_hit': True, 'structure_top1': ('miso-soybean', 0.507, 'method')}

{'id': 'q07', 'question': 'What is the allergen note for the homemade miso paste recipe?', 'recipe_id': 'miso-soybean', 'section': 'allergen', 'keyword': 'soy', 'baseline_hit': True, 'baseline_top1': ('miso-soybean', 0.618), 'structure_hit': True, 'structure_top1': ('miso-soybean', 0.629, 'ingredients')}

{'id': 'q08', 'question': 'Which cuisine is the classic sauerkraut recipe associated with?', 'recipe_id': 'sauerkraut-classic', 'section': 'ingredients', 'keyword': 'German', 'baseline_hit': True, 'baseline_top1': ('sauerkraut-classic', 0.765), 'structure_hit': True, 'structure_top1': ('sauerkraut-classic', 0.766, 'ingredients')}


filter query: Which recipe uses a live starter culture incubated with milk to make a creamy fermented dish?
unfiltered: [('yogurt-dairy', 0.535), ('yogurt-dairy', 0.527), ('miso-soybean', 0.381), ('sourdough-2kg', 0.379), ('kombucha-ginger', 0.356)]
filtered:   [('miso-soybean', 0.381), ('sourdough-2kg', 0.379), ('kombucha-ginger', 0.356), ('sourdough-2kg', 0.354), ('miso-soybean', 0.326)]

{'question': 'How much fine sea salt does the 2kg sourdough recipe use?', 'answer': 'The 2 kg sourdough recipe uses **7 g of fine sea salt**. [source: sourdough-2kg.pdf p.1]', 'refused': False, 'citation': {'chunk_id': '66f924e04426674c6c705fb191b3a85cbe0fa365', 'source_file': 'sourdough-2kg.pdf', 'page': 1, 'snippet': '2kg Country Sourdough Loaf Cuisine: Western / Artisan Bread | Dietary: vegan Ingredients: Bread flour  1000 g  (100%) Water  750 g  (75%) Fine sea salt  7 g  (0.35%) Active starter  200 g  (20%)', 'score': 0.5967}, 'resolved_recipe_id': 'sourdough-2kg', 'claim_in_resolved_text': True}

{'question': 'What temperature should the milk be heated to when making homemade yogurt?', 'answer': 'The milk should be heated to 85 °C. [source: yogurt-dairy.pdf p.1]', 'refused': False, 'citation': {'chunk_id': 'd8100cb58ce96833b171ef66fb12fd5505762580', 'source_file': 'yogurt-dairy.pdf', 'page': 1, 'snippet': 'Homemade Dairy Yogurt Method: Heat the milk to 85 C, stirring occasionally to prevent scorching, then cool to 43-46 C. Whisk in the live starter culture until fully dissolved. Pour into a clean container, cover, and incubate at 43-46 C for 6 to 8 hours until set, without disturbi', 'score': 0.7213}, 'resolved_recipe_id': 'yogurt-dairy', 'claim_in_resolved_text': True}

{'question': 'What is the allergen note for the homemade miso paste recipe?', 'answer': 'Allergens: Contains soy. Produced with koji (Aspergillus oryzae); no gluten-containing grains used. [source: miso-soybean.pdf p.1]', 'refused': False, 'citation': {'chunk_id': 'e55c9e6a2e61dd487890ef19ab4cfbebe07f99f2', 'source_file': 'miso-soybean.pdf', 'page': 1, 'snippet': 'Homemade Soybean Miso Paste Method: Soak and cook the soybeans until very tender, then mash while still warm. Mix the koji rice thoroughly with the salt. Combine the mashed soybeans, salted koji and reserved cooking liquid into a firm, moldable paste. Pack tightly into a clean cr', 'score': 0.5431}, 'resolved_recipe_id': 'miso-soybean', 'claim_in_resolved_text': True}

{'question': 'What is the exact calorie count of the 2kg sourdough loaf?', 'answer': "I couldn't find enough information in the provided recipes to answer that question.", 'refused': True}

{'question': 'How many grams of protein does the napa cabbage kimchi recipe contain per serving?', 'answer': "I couldn't find enough information in the provided recipes to answer that question.", 'refused': True}

{'question': 'What is the vitamin B12 content of the homemade soybean miso paste?', 'answer': "I couldn't find enough information in the provided recipes to answer that question.", 'refused': True}

bonus question: How much fine sea salt does the sourdough recipe use, and at what point in the process is it added?
baseline top1: [('sourdough-2kg', None, 0.547), ('sauerkraut-classic', None, 0.514), ('miso-soybean', None, 0.454)]
baseline answer: The sourdough recipe calls for **7 g of fine sea salt**. The recipe does not specify a particular point in the process where the salt is added. [source: sourdough-2kg.pdf p.1]
structure top1: [('sourdough-2kg', 'ingredients', 0.531), ('sourdough-2kg', 'method', 0.443), ('sourdough-2kg', 'allergen', 0.388)]
structure answer: The recipe calls for **7 g of fine sea salt** (0.35 % of the flour).  
It is added together with the starter and mixed in after the initial autolyse, before the bulk fermentation begins. [source: sourdough-2kg.pdf p.1]
