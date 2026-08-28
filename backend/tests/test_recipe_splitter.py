"""The recipe-aware splitter for cookbook-style PDFs (many recipes per page)."""
from langchain_core.documents import Document

from rag.ingestion.recipe_splitter import split_recipes

# One page, three recipes back-to-back - the shape a blind splitter mangles.
COOKBOOK_PAGE = Document(
    page_content=(
        "5\n"
        "Oatmeal Buns\n"
        "Harriet Stanley\n"
        "1 cup quick oatmeal\n"
        "2 cups boiling water\n"
        "Mix and bake 20 minutes at 350.\n"
        "Oatmeal Bread\n"
        "DoLores Kounovsky\n"
        "2 packages dry yeast\n"
        "1 cup warm water\n"
        "1/4 cup dark molasses\n"
        "Combine, knead, and bake at 375 for 35-40 minutes.\n"
        "Whole Wheat Bread\n"
        "Alice Sullivan\n"
        "4 cups whole wheat flour\n"
        "7 cups white flour\n"
        "Bake 1 hour in a 375 oven.\n"
    ),
    metadata={"source_file": "cookbook.pdf", "page": 5, "title": "Family Cookbook"},
)

SINGLE_RECIPE_PAGE = Document(
    page_content=(
        "Chicken Biryani Recipe\n"
        "Servings: 4  Prep: 25 minutes  Cook: 45 minutes\n"
        "Ingredients\nBasmati rice 2 cups\nChicken 500 g\n"
        "Instructions\n1. Soak the rice.\n2. Fry the onions.\n"
    ),
    metadata={"source_file": "biryani.pdf", "page": 1, "title": "biryani.pdf"},
)


def test_each_recipe_becomes_its_own_titled_chunk():
    chunks = split_recipes([COOKBOOK_PAGE])
    assert chunks is not None
    titles = [c.metadata["recipe_title"] for c in chunks]
    assert titles == ["Oatmeal Buns", "Oatmeal Bread", "Whole Wheat Bread"]


def test_oatmeal_bread_chunk_carries_its_name_and_full_recipe():
    chunks = split_recipes([COOKBOOK_PAGE])
    bread = next(c for c in chunks if c.metadata["recipe_title"] == "Oatmeal Bread")
    # the title travels with the ingredients + method - the whole point
    assert bread.page_content.startswith("Oatmeal Bread")
    assert "dark molasses" in bread.page_content
    assert "bake at 375" in bread.page_content.lower()
    # and NOT the neighbouring recipe's ingredients
    assert "quick oatmeal" not in bread.page_content
    assert "whole wheat flour" not in bread.page_content
    assert bread.metadata["page"] == 5


def test_single_recipe_pdf_falls_back_to_the_normal_splitter():
    assert split_recipes([SINGLE_RECIPE_PAGE]) is None
