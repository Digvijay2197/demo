"""Generate sample recipe PDFs into data/pdfs/ for trying out the RAG bot.

These stand in for "any recipe PDF you drop in the folder" - text-based,
multi-section, with quantities the bot can be quizzed on. Regenerate any time:

    python scripts/generate_sample_pdfs.py

Then index them with:  python scripts/ingest.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())

import pymupdf  # PyMuPDF

from rag.config import PDF_DIR

RECIPES = [
    {
        "filename": "neapolitan-margherita-pizza.pdf",
        "title": "Neapolitan Margherita Pizza",
        "meta": {
            "Cuisine": "Italian",
            "Serves": "4 (two 30 cm pizzas)",
            "Prep time": "30 minutes, plus 24 hours cold proof",
            "Cook time": "90 seconds per pizza at 450 C (or 8-10 minutes at 250 C)",
            "Dietary": "vegetarian; contains gluten and dairy",
        },
        "sections": [
            (
                "Dough ingredients (makes 2 balls of 280 g)",
                [
                    "500 g Italian 00 flour (W300 strength if available)",
                    "325 g cold water (65% hydration)",
                    "10 g fine sea salt",
                    "2 g fresh yeast, or 0.7 g active dry yeast",
                ],
            ),
            (
                "Topping ingredients (per pizza)",
                [
                    "80 g San Marzano tomatoes, hand-crushed, lightly salted",
                    "70 g fresh cow's-milk mozzarella (fior di latte), torn and drained",
                    "4-5 fresh basil leaves",
                    "1 teaspoon extra-virgin olive oil",
                    "A pinch of sea salt",
                ],
            ),
            (
                "Method",
                [
                    "Dissolve the yeast in the water. Add the flour and mix until no dry spots remain, then rest 20 minutes.",
                    "Add the salt and knead 10-12 minutes until smooth and elastic. The dough should pass a windowpane test.",
                    "Bulk ferment at room temperature for 2 hours, then divide into two 280 g balls.",
                    "Place the balls in a covered container and cold-proof in the fridge for 24 hours (up to 72).",
                    "Remove the dough 2 hours before baking and let it come to room temperature.",
                    "Stretch one ball by hand to 30 cm, leaving a 1.5 cm border for the cornicione. Do not use a rolling pin.",
                    "Spread 80 g crushed tomato, add the mozzarella, drizzle with olive oil.",
                    "Bake at maximum heat until the crust is blistered and charred in spots. Finish with fresh basil.",
                ],
            ),
            (
                "Notes",
                [
                    "Allergens: wheat (gluten) in the dough, dairy in the mozzarella.",
                    "For a vegan version, replace the mozzarella with a cashew-based alternative; the dough is already vegan.",
                    "The 24-hour cold proof is what develops flavour and digestibility - do not skip it.",
                ],
            ),
        ],
    },
    {
        "filename": "thai-green-chicken-curry.pdf",
        "title": "Thai Green Chicken Curry (Gaeng Keow Wan Gai)",
        "meta": {
            "Cuisine": "Thai",
            "Serves": "4 with steamed jasmine rice",
            "Prep time": "20 minutes",
            "Cook time": "25 minutes",
            "Dietary": "gluten-free; contains fish and shellfish (in the curry paste)",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "4 tablespoons Thai green curry paste (about 60 g)",
                    "400 ml full-fat coconut milk",
                    "500 g boneless chicken thigh, sliced 1 cm thick",
                    "2 tablespoons fish sauce",
                    "1 tablespoon palm sugar, chopped",
                    "150 g Thai apple eggplant, quartered",
                    "100 g bamboo shoots, drained and rinsed",
                    "4 kaffir lime leaves, torn",
                    "1 large red chilli, sliced on the bias",
                    "A handful of Thai sweet basil leaves",
                ],
            ),
            (
                "Method",
                [
                    "Spoon the thick coconut cream from the top of the can into a wok over medium heat and simmer 3-4 minutes until it splits and the oil surfaces.",
                    "Add the green curry paste and fry 2 minutes until deeply fragrant.",
                    "Add the chicken and stir to coat, cooking 3 minutes until the outside turns opaque.",
                    "Pour in the remaining coconut milk plus 150 ml water. Bring to a gentle simmer.",
                    "Season with the fish sauce and palm sugar. Add the eggplant, bamboo shoots and lime leaves.",
                    "Simmer 12-15 minutes until the eggplant is tender and the chicken is cooked through.",
                    "Turn off the heat, stir through the basil and sliced chilli, and serve with jasmine rice.",
                ],
            ),
            (
                "Notes",
                [
                    "Allergens: fish sauce (fish) and shrimp paste inside most green curry pastes (shellfish).",
                    "Vegetarian swap: use a shrimp-paste-free paste, replace fish sauce with light soy plus a little salt, and use firm tofu and vegetables instead of chicken.",
                    "Do not boil hard after adding the basil or the curry will dull in colour and aroma.",
                ],
            ),
        ],
    },
    {
        # Near-duplicate name pair (with "Old Norwegian Lefse" below) - same
        # dish, different numbers, on purpose: a question about one that
        # doesn't say *which* can pull both chunks into context and tempt the
        # model to answer with the other recipe's figures.
        "filename": "classic-lefse.pdf",
        "title": "Classic Lefse",
        "meta": {
            "Cuisine": "Norwegian",
            "Serves": "8 (about 12 rounds)",
            "Prep time": "45 minutes, plus 1 hour dough rest",
            "Cook time": "1-2 minutes per side on a dry griddle at 450 F",
            "Dietary": "vegetarian; contains dairy and gluten",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "2.5 lb russet potatoes, boiled and riced while hot",
                    "1/2 cup butter",
                    "1/4 cup heavy cream",
                    "1 teaspoon fine sea salt",
                    "1.5 cups all-purpose flour, plus more for rolling",
                ],
            ),
            (
                "Method",
                [
                    "Rice the hot boiled potatoes into a bowl and stir in the butter, cream and salt.",
                    "Let the mixture cool completely, then work in the flour until a soft dough just comes together.",
                    "Rest the dough for 1 hour at room temperature before rolling.",
                    "Roll paper-thin rounds on a floured cloth.",
                    "Cook on a dry griddle at 450 F for 1-2 minutes per side until light brown spots appear.",
                    "Stack the finished rounds under a towel to keep them soft.",
                ],
            ),
            (
                "Notes",
                [
                    "Freezes well stacked between sheets of wax paper.",
                    "Allergens: dairy, gluten.",
                ],
            ),
        ],
    },
    {
        "filename": "old-norwegian-lefse.pdf",
        "title": "Old Norwegian Lefse",
        "meta": {
            "Cuisine": "Norwegian (heirloom)",
            "Serves": "10 (about 16 rounds)",
            "Prep time": "1 hour, plus an overnight chill",
            "Cook time": "45 seconds per side on a hot dry griddle at 375 F",
            "Dietary": "vegetarian; contains dairy and gluten",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "3 lb Yukon Gold potatoes, boiled and riced while hot",
                    "1/3 cup lard (or shortening)",
                    "1/3 cup whole milk",
                    "1 tablespoon sugar",
                    "1 teaspoon fine sea salt",
                    "2 cups all-purpose flour",
                ],
            ),
            (
                "Method",
                [
                    "Rice the potatoes while still hot and stir in the lard, milk, sugar and salt.",
                    "Chill the mixture overnight - this, not a short rest, is what keeps the dough tender.",
                    "The next day, work in the flour just until it holds together; overworking toughens it.",
                    "Roll very thin on a floured cloth.",
                    "Cook on a hot dry griddle at 375 F for about 45 seconds per side until brown spots appear.",
                    "Keep the rounds warm wrapped in a towel.",
                ],
            ),
            (
                "Notes",
                [
                    "An heirloom family recipe passed down for four generations.",
                    "Serve with butter, sugar and cinnamon.",
                ],
            ),
        ],
    },
    {
        # Exact-code case: "SD-2041" is a rare token a dense embedding barely
        # weights, but BM25 nails it. Also a near-neighbor of the two breads
        # below, to test that hybrid search doesn't just win on codes but
        # doesn't lose the plain "bread" queries either.
        "filename": "sourdough-loaf-batch-sd-2041.pdf",
        "title": "Sourdough Loaf (Batch SD-2041)",
        "meta": {
            "Cuisine": "Artisan bread",
            "Serves": "1 loaf (about 10 slices)",
            "Prep time": "30 minutes active, plus an 18 hour bulk ferment",
            "Cook time": "45 minutes at 230 C",
            "Dietary": "vegetarian, vegan; contains gluten",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "500 g bread flour",
                    "375 g water (75% hydration)",
                    "100 g active sourdough starter",
                    "10 g fine sea salt",
                ],
            ),
            (
                "Method",
                [
                    "Mix the flour and water and autolyse for 30 minutes.",
                    "Add the starter and salt, then stretch and fold every 30 minutes for the first 2 hours.",
                    "Bulk ferment 18 hours at room temperature.",
                    "Shape into a boule and cold-proof in the fridge for 1 hour.",
                    "Score, then bake covered at 230 C for 20 minutes.",
                    "Uncover and bake 25 more minutes until deep brown.",
                ],
            ),
            (
                "Notes",
                [
                    "This batch's internal QA code is SD-2041; the oven was calibrated and its log kept under that code.",
                    "If your starter is sluggish, extend the bulk ferment by 2-3 hours rather than adding commercial yeast.",
                ],
            ),
        ],
    },
    {
        "filename": "kimchi-fried-rice-gochugaru.pdf",
        "title": "Kimchi Fried Rice with Gochugaru",
        "meta": {
            "Cuisine": "Korean-inspired",
            "Serves": "2",
            "Prep time": "10 minutes",
            "Cook time": "15 minutes",
            "Dietary": "vegetarian option available; contains gluten (soy sauce) and egg",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "2 cups day-old cooked rice",
                    "1 cup chopped napa cabbage kimchi",
                    "2 tablespoons gochugaru (Korean red chilli flakes)",
                    "1 tablespoon gochujang",
                    "2 tablespoons soy sauce",
                    "1 tablespoon toasted sesame oil",
                    "2 eggs",
                    "2 scallions, sliced",
                    "1 tablespoon neutral oil",
                ],
            ),
            (
                "Method",
                [
                    "Heat the neutral oil in a wok and fry the kimchi for 2 minutes.",
                    "Stir in the gochugaru and gochujang.",
                    "Add the rice and soy sauce; fry 5 minutes until the rice is coated and slightly crisp.",
                    "Push the rice aside and fry the eggs sunny-side up in the same wok.",
                    "Top the rice with the eggs, scallions and a drizzle of sesame oil.",
                ],
            ),
            (
                "Notes",
                [
                    "For a vegetarian version, use vegetarian kimchi and skip the egg, or keep it for protein.",
                    "Gochugaru is milder and fruitier than generic chilli flakes - do not substitute cayenne 1:1; use about half as much.",
                ],
            ),
        ],
    },
    {
        "filename": "rustic-country-bread.pdf",
        "title": "Rustic Country Bread",
        "meta": {
            "Cuisine": "European farmhouse",
            "Serves": "1 loaf (about 12 slices)",
            "Prep time": "20 minutes, plus a 3 hour rise",
            "Cook time": "40 minutes at 220 C",
            "Dietary": "vegetarian, vegan; contains gluten",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "450 g bread flour",
                    "50 g whole wheat flour",
                    "350 g water",
                    "7 g instant yeast",
                    "10 g fine sea salt",
                ],
            ),
            (
                "Method",
                [
                    "Mix the flours, water and yeast; rest 20 minutes.",
                    "Add the salt and knead 8 minutes.",
                    "Bulk rise 2 hours until doubled.",
                    "Shape into a round loaf and proof 45 minutes.",
                    "Bake at 220 C for 40 minutes until the loaf sounds hollow when tapped.",
                ],
            ),
            (
                "Notes",
                [
                    "A fast, everyday loaf - no starter needed.",
                    "Freezes well, sliced.",
                ],
            ),
        ],
    },
    {
        "filename": "honey-oat-sandwich-bread.pdf",
        "title": "Honey Oat Sandwich Bread",
        "meta": {
            "Cuisine": "American",
            "Serves": "1 loaf (about 16 slices)",
            "Prep time": "20 minutes, plus a 2 hour rise",
            "Cook time": "35 minutes at 190 C",
            "Dietary": "vegetarian; contains gluten and dairy",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "400 g bread flour",
                    "100 g rolled oats, plus extra for topping",
                    "280 g warm milk",
                    "60 g honey",
                    "30 g unsalted butter, melted",
                    "7 g instant yeast",
                    "8 g fine sea salt",
                ],
            ),
            (
                "Method",
                [
                    "Combine the milk, honey and yeast; rest 5 minutes.",
                    "Add the flour, oats, butter and salt; knead 10 minutes.",
                    "Rise 1.5 hours until doubled.",
                    "Shape into a loaf pan, top with extra oats, and proof 30 minutes.",
                    "Bake at 190 C for 35 minutes until golden and 90 C internal.",
                ],
            ),
            (
                "Notes",
                [
                    "Swap the honey for maple syrup 1:1 for a vegan-friendlier version (the butter still needs a plant-based swap).",
                ],
            ),
        ],
    },
    {
        # Exact-code case in a plainer, single-word-searchable form.
        "filename": "pantry-chili-con-carne-rec-118.pdf",
        "title": "Pantry Chili con Carne (Recipe Card REC-118)",
        "meta": {
            "Cuisine": "Tex-Mex",
            "Serves": "6",
            "Prep time": "15 minutes",
            "Cook time": "1.5 hours",
            "Dietary": "gluten-free; contains beef",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "900 g ground beef",
                    "2 onions, diced",
                    "3 cloves garlic, minced",
                    "2 tablespoons chilli powder",
                    "1 tablespoon ground cumin",
                    "2 cans (400 g each) crushed tomatoes",
                    "2 cans (400 g each) kidney beans, drained",
                    "1 cup beef stock",
                    "salt, to taste",
                ],
            ),
            (
                "Method",
                [
                    "Brown the beef with the onion and garlic.",
                    "Stir in the chilli powder and cumin and toast for 1 minute.",
                    "Add the tomatoes, beans and stock.",
                    "Simmer uncovered for 1.5 hours, stirring occasionally.",
                    "Season with salt to taste.",
                ],
            ),
            (
                "Notes",
                [
                    "Filed as recipe card REC-118 in the pantry binder.",
                    "Freezes well for up to 3 months.",
                    "For a vegetarian version, swap the beef for 2 extra cans of beans and use vegetable stock.",
                ],
            ),
        ],
    },
    {
        "filename": "miso-glazed-salmon.pdf",
        "title": "Miso-Glazed Salmon",
        "meta": {
            "Cuisine": "Japanese-inspired",
            "Serves": "4",
            "Prep time": "10 minutes, plus a 30 minute marinate",
            "Cook time": "12 minutes",
            "Dietary": "gluten-free option (use tamari); contains fish and soy",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "4 salmon fillets (about 150 g each)",
                    "3 tablespoons white shiro miso",
                    "2 tablespoons mirin",
                    "1 tablespoon sake",
                    "1 tablespoon sugar",
                    "1 teaspoon soy sauce",
                ],
            ),
            (
                "Method",
                [
                    "Whisk the miso, mirin, sake, sugar and soy sauce into a glaze.",
                    "Marinate the salmon in the glaze for 30 minutes.",
                    "Broil 10-12 minutes until the glaze caramelises and the fish flakes easily.",
                ],
            ),
            (
                "Notes",
                [
                    "Shiro (white) miso is sweeter and milder than red miso - do not substitute red miso 1:1; use about two-thirds the amount.",
                    "For gluten-free, use tamari instead of soy sauce.",
                ],
            ),
        ],
    },
    # --- Decoys below: same theme/vocabulary as a case above, on purpose, so
    # a plain "bread"/"fried rice"/"glazed"/"chili" query has real competition
    # in top-3 and only the exact code or rare ingredient in the question
    # actually disambiguates. Without these, the small corpus was too easy -
    # semantic search alone already won every case. ---
    {
        "filename": "everyday-white-sandwich-bread.pdf",
        "title": "Everyday White Sandwich Bread",
        "meta": {
            "Cuisine": "American", "Serves": "1 loaf (16 slices)",
            "Prep time": "15 minutes, plus a 2 hour rise", "Cook time": "30 minutes at 190 C",
            "Dietary": "vegetarian; contains gluten and dairy",
        },
        "sections": [
            ("Ingredients", [
                "500 g bread flour", "320 g water (64% hydration)", "7 g instant yeast",
                "25 g sugar", "20 g butter", "8 g fine sea salt",
            ]),
            ("Method", [
                "Mix flour, water and yeast; rest 20 minutes.",
                "Add sugar, butter and salt; knead 10 minutes.",
                "Rise 1.5 hours until doubled, shape into a loaf pan, proof 30 minutes.",
                "Bake at 190 C for 30 minutes until golden.",
            ]),
            ("Notes", ["A soft everyday loaf; keeps 4 days wrapped at room temperature."]),
        ],
    },
    {
        "filename": "whole-wheat-farmhouse-loaf.pdf",
        "title": "Whole Wheat Farmhouse Loaf",
        "meta": {
            "Cuisine": "American farmhouse", "Serves": "1 loaf (14 slices)",
            "Prep time": "20 minutes, plus a 2.5 hour rise", "Cook time": "35 minutes at 200 C",
            "Dietary": "vegetarian, vegan; contains gluten",
        },
        "sections": [
            ("Ingredients", [
                "350 g whole wheat flour", "150 g bread flour", "340 g water (68% hydration)",
                "7 g instant yeast", "10 g honey", "9 g fine sea salt",
            ]),
            ("Method", [
                "Mix flours, water, yeast and honey; rest 20 minutes.",
                "Add salt; knead 10 minutes.",
                "Rise 1.5 hours, shape, proof 45 minutes.",
                "Bake at 200 C for 35 minutes.",
            ]),
            ("Notes", ["Denser crumb than white bread; hydration runs a touch higher to keep the whole wheat from drying out."]),
        ],
    },
    {
        "filename": "no-knead-dutch-oven-bread.pdf",
        "title": "No-Knead Dutch Oven Bread",
        "meta": {
            "Cuisine": "Rustic artisan", "Serves": "1 loaf (12 slices)",
            "Prep time": "10 minutes active, plus a 12-18 hour rest",
            "Cook time": "45 minutes at 230 C in a covered dutch oven",
            "Dietary": "vegetarian, vegan; contains gluten",
        },
        "sections": [
            ("Ingredients", [
                "400 g bread flour", "320 g water (80% hydration)", "2 g instant yeast", "8 g fine sea salt",
            ]),
            ("Method", [
                "Stir everything together and rest covered 12-18 hours at room temperature.",
                "Turn onto a floured surface, shape loosely, rest 30 minutes.",
                "Bake covered in a preheated dutch oven at 230 C for 30 minutes.",
                "Uncover and bake 15 more minutes until deep brown.",
            ]),
            ("Notes", ["The long slow rise builds flavour without kneading - the highest hydration of the house breads."]),
        ],
    },
    {
        "filename": "vegetable-fried-rice.pdf",
        "title": "Vegetable Fried Rice",
        "meta": {
            "Cuisine": "Chinese-American", "Serves": "4", "Prep time": "15 minutes", "Cook time": "10 minutes",
            "Dietary": "vegetarian; vegan option; contains egg and gluten (soy sauce)",
        },
        "sections": [
            ("Ingredients", [
                "4 cups day-old cooked rice", "1 cup diced carrot and peas", "2 eggs",
                "3 tablespoons soy sauce", "1 tablespoon sesame oil", "2 scallions, sliced", "2 tablespoons neutral oil",
            ]),
            ("Method", [
                "Scramble the eggs in the neutral oil and set aside.",
                "Stir-fry the carrot and peas 2 minutes.",
                "Add the rice and soy sauce; toss 4 minutes.",
                "Fold in the eggs and scallions; drizzle with sesame oil.",
            ]),
            ("Notes", ["For vegan, omit the eggs and add extra vegetables or firm tofu."]),
        ],
    },
    {
        "filename": "thai-basil-chicken-stir-fry.pdf",
        "title": "Thai Basil Chicken Stir-Fry (Pad Krapow Gai)",
        "meta": {
            "Cuisine": "Thai", "Serves": "2", "Prep time": "10 minutes", "Cook time": "10 minutes",
            "Dietary": "gluten-free option (use tamari); contains fish",
        },
        "sections": [
            ("Ingredients", [
                "400 g ground chicken", "4 cloves garlic, minced", "3-4 Thai chillies, minced",
                "2 tablespoons fish sauce", "1 tablespoon oyster sauce", "1 teaspoon sugar",
                "1 cup Thai holy basil leaves", "2 tablespoons neutral oil", "2 fried eggs, to serve",
            ]),
            ("Method", [
                "Fry the garlic and chillies in the oil 1 minute.",
                "Add the chicken and cook through, breaking it up.",
                "Season with fish sauce, oyster sauce and sugar.",
                "Stir in the basil off heat.",
                "Serve over rice topped with a fried egg.",
            ]),
            ("Notes", ["Holy basil is more peppery than sweet Thai basil; sweet basil is an acceptable substitute in a pinch."]),
        ],
    },
    {
        "filename": "korean-bulgogi-rice-bowl.pdf",
        "title": "Korean Bulgogi Rice Bowl",
        "meta": {
            "Cuisine": "Korean", "Serves": "4", "Prep time": "30 minute marinate", "Cook time": "10 minutes",
            "Dietary": "contains soy and sesame",
        },
        "sections": [
            ("Ingredients", [
                "600 g thinly sliced beef sirloin", "1/3 cup soy sauce", "2 tablespoons brown sugar",
                "1 tablespoon sesame oil", "1 Asian pear, grated", "4 cloves garlic, minced",
                "4 cups steamed rice", "sliced scallions and sesame seeds, to serve",
            ]),
            ("Method", [
                "Marinate the beef in soy sauce, sugar, sesame oil, pear and garlic for 30 minutes.",
                "Sear in a hot pan 3-4 minutes.",
                "Serve over rice topped with scallions and sesame seeds.",
            ]),
            ("Notes", ["The grated pear tenderises the beef and adds sweetness; do not marinate longer than a few hours or the meat turns mushy."]),
        ],
    },
    {
        "filename": "teriyaki-glazed-chicken-thighs.pdf",
        "title": "Teriyaki Glazed Chicken Thighs",
        "meta": {
            "Cuisine": "Japanese-inspired", "Serves": "4", "Prep time": "10 minutes", "Cook time": "20 minutes",
            "Dietary": "contains soy",
        },
        "sections": [
            ("Ingredients", [
                "8 boneless chicken thighs", "1/3 cup soy sauce", "1/4 cup mirin",
                "2 tablespoons sugar", "1 tablespoon sake", "1 teaspoon grated ginger",
            ]),
            ("Method", [
                "Whisk the sauce ingredients together.",
                "Sear the chicken skin-side down 6 minutes.",
                "Flip, pour in the sauce and simmer 10 minutes until glazed and sticky.",
            ]),
            ("Notes", ["Mirin's sweetness is what makes the glaze stick - a dry sherry with extra sugar is the closest substitute."]),
        ],
    },
    {
        "filename": "soy-ginger-glazed-cod.pdf",
        "title": "Soy-Ginger Glazed Cod",
        "meta": {
            "Cuisine": "Japanese-inspired", "Serves": "4",
            "Prep time": "10 minutes, plus a 20 minute marinate", "Cook time": "10 minutes",
            "Dietary": "contains fish and soy",
        },
        "sections": [
            ("Ingredients", [
                "4 cod fillets", "3 tablespoons soy sauce", "2 tablespoons mirin",
                "1 tablespoon grated ginger", "1 tablespoon honey", "1 teaspoon sesame oil",
            ]),
            ("Method", [
                "Whisk the marinade ingredients.",
                "Marinate the cod 20 minutes.",
                "Pan-sear or broil 8-10 minutes, basting with the marinade, until glazed and opaque.",
            ]),
            ("Notes", ["A milder, faster cousin of a miso glaze - no fermented paste involved."]),
        ],
    },
    {
        "filename": "weeknight-beef-and-bean-chili.pdf",
        "title": "Weeknight Beef and Bean Chili",
        "meta": {
            "Cuisine": "Tex-Mex", "Serves": "6", "Prep time": "10 minutes", "Cook time": "40 minutes",
            "Dietary": "gluten-free; contains beef",
        },
        "sections": [
            ("Ingredients", [
                "700 g ground beef", "1 onion, diced", "2 tablespoons chilli powder", "1 teaspoon ground cumin",
                "1 can (400 g) crushed tomatoes", "1 can (400 g) black beans, drained", "salt, to taste",
            ]),
            ("Method", [
                "Brown the beef and onion.",
                "Stir in the chilli powder and cumin.",
                "Add the tomatoes and beans; simmer 30 minutes.",
                "Season with salt to taste.",
            ]),
            ("Notes", ["A faster, simpler cousin of the pantry chili card - no long simmer needed."]),
        ],
    },
    {
        "filename": "slow-cooker-beef-stew.pdf",
        "title": "Slow Cooker Beef Stew",
        "meta": {
            "Cuisine": "American comfort food", "Serves": "6", "Prep time": "20 minutes", "Cook time": "8 hours on low",
            "Dietary": "gluten-free; contains beef",
        },
        "sections": [
            ("Ingredients", [
                "1 kg beef chuck, cubed", "4 carrots, chopped", "3 potatoes, chopped", "1 onion, chopped",
                "2 cups beef stock", "2 tablespoons tomato paste", "2 bay leaves",
            ]),
            ("Method", [
                "Sear the beef.",
                "Combine everything in the slow cooker.",
                "Cook on low for 8 hours until the beef is fork-tender.",
            ]),
            ("Notes", ["No chilli powder in this one - it's a stew, not a chili, despite both starting with browned beef and onion."]),
        ],
    },
]

_CSS = """
* { font-family: sans-serif; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 4px 0; }
table { margin: 6px 0 14px 0; border-collapse: collapse; }
td { font-size: 10.5px; padding: 1px 10px 1px 0; vertical-align: top; }
td.k { color: #555; white-space: nowrap; }
h2 { font-size: 13px; margin: 14px 0 4px 0; border-bottom: 1px solid #bbb; padding-bottom: 2px; }
ol, ul { margin: 4px 0 4px 0; padding-left: 20px; }
li { font-size: 11px; margin: 3px 0; line-height: 1.35; }
"""


def _recipe_html(recipe: dict) -> str:
    meta_rows = "".join(
        f"<tr><td class='k'>{k}</td><td>{v}</td></tr>" for k, v in recipe["meta"].items()
    )
    blocks = [f"<h1>{recipe['title']}</h1>", f"<table>{meta_rows}</table>"]
    for heading, items in recipe["sections"]:
        tag = "ol" if heading.lower().startswith("method") else "ul"
        lis = "".join(f"<li>{it}</li>" for it in items)
        blocks.append(f"<h2>{heading}</h2><{tag}>{lis}</{tag}>")
    return f"<style>{_CSS}</style>" + "".join(blocks)


def _write_pdf(recipe: dict, out_dir: str) -> str:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 portrait, points
    rect = pymupdf.Rect(50, 50, 545, 792)
    result = page.insert_htmlbox(rect, _recipe_html(recipe))
    spare_height = result[0] if isinstance(result, (tuple, list)) else result
    if spare_height is not None and spare_height < 0:
        print(f"  warning: {recipe['filename']} content was scaled to fit one page")

    path = os.path.join(out_dir, recipe["filename"])
    doc.set_metadata({"title": recipe["title"], "subject": "Sample recipe for the RAG demo"})
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    return path


def main() -> None:
    os.makedirs(PDF_DIR, exist_ok=True)
    for recipe in RECIPES:
        path = _write_pdf(recipe, PDF_DIR)
        size_kb = os.path.getsize(path) / 1024
        print(f"wrote {path}  ({size_kb:.1f} KB)")
    print(f"\n{len(RECIPES)} sample PDFs in {PDF_DIR}")
    print("Next: python scripts/ingest.py")


if __name__ == "__main__":
    main()
