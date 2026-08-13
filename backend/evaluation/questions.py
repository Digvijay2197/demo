from rag.retrieval.evaluation import KnownAnswerQuestion

# These 8 questions were written directly from the recipe card source
# files BEFORE any retrieval was run against either chunker. At least
# 3 depend on an ingredient-table row (marked ingredient_dependent).
KNOWN_ANSWER_QUESTIONS = [
    KnownAnswerQuestion(
        id="q01",
        question="How much fine sea salt does the 2kg sourdough recipe use?",
        expected_answer="7g (0.35% baker's percentage)",
        recipe_id="sourdough-2kg",
        section="ingredients",
        ingredient_dependent=True,
        expected_keyword="7g",
    ),
    KnownAnswerQuestion(
        id="q02",
        question="What is the hydration percentage of the 2kg sourdough recipe?",
        expected_answer="75% (1500g water at 75% baker's percentage)",
        recipe_id="sourdough-2kg",
        section="ingredients",
        ingredient_dependent=True,
        expected_keyword="75%",
    ),
    KnownAnswerQuestion(
        id="q03",
        question="What is the weight of coarse sea salt used in the kimchi recipe?",
        expected_answer="50g",
        recipe_id="kimchi-napa",
        section="ingredients",
        ingredient_dependent=True,
        expected_keyword="50g",
    ),
    KnownAnswerQuestion(
        id="q04",
        question="How much white sugar is used to brew the kombucha?",
        expected_answer="100g (10% of the water weight)",
        recipe_id="kombucha-ginger",
        section="ingredients",
        ingredient_dependent=True,
        expected_keyword="100g",
    ),
    KnownAnswerQuestion(
        id="q05",
        question="What temperature should the milk be heated to when making homemade yogurt?",
        expected_answer="85C",
        recipe_id="yogurt-dairy",
        section="method",
        ingredient_dependent=False,
        expected_keyword="85c",
    ),
    KnownAnswerQuestion(
        id="q06",
        question="How long should the homemade miso ferment before it is ready?",
        expected_answer="6-12 months in a cool, dark place",
        recipe_id="miso-soybean",
        section="method",
        ingredient_dependent=False,
        expected_keyword="6-12 months",
    ),
    KnownAnswerQuestion(
        id="q07",
        question="What is the allergen note for the homemade miso paste recipe?",
        expected_answer=(
            "Contains soy; produced with koji (Aspergillus oryzae cultured rice), "
            "no gluten-containing grains used"
        ),
        recipe_id="miso-soybean",
        section="allergen",
        ingredient_dependent=False,
        expected_keyword="soy",
    ),
    KnownAnswerQuestion(
        id="q08",
        question="Which cuisine is the classic sauerkraut recipe associated with?",
        expected_answer="German",
        recipe_id="sauerkraut-classic",
        section="metadata",
        ingredient_dependent=False,
        expected_keyword="german",
    ),
]

# Questions whose answers do not exist anywhere in the recipe corpus. The chatbot must refuse.
OUT_OF_CORPUS_QUESTIONS = [
    "What is the exact calorie count of the 2kg sourdough loaf?",
    "How many grams of protein does the napa cabbage kimchi recipe contain per serving?",
    "What is the vitamin B12 content of the homemade soybean miso paste?",
]

# Subset of the 8 known-answer questions run through full grounded generation.
GROUNDED_QUESTION_IDS = ["q01", "q05", "q07"]
