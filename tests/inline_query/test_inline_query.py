"""Test inline query logic."""
import pytest
from tests.factories import sticker_factory

from stickerfinder.models import Tag
from stickerfinder.telegram.inline_query.context import Context
from stickerfinder.telegram.inline_query.search import get_matching_stickers


@pytest.mark.parametrize(
    "query, first_score, second_score",
    [
        ("testtag", 1, 1),
        ("awesome dumb", 0.75, 0.75),
        ("testtag roflcopter", 2.00, 1.00),
        ("awesome dumb testtag roflcopter", 2.75, 1.75),
        ("awesome testtag roflcopter", 2.00, 1.75),
    ],
)
def test_strict_sticker_search_set_order(
    session, tg_context, strict_inline_search, user, query, first_score, second_score
):
    """Test correct sticker set sorting order."""
    # Simple search which should get nearly all stickers from both sets
    context = Context(tg_context, query, "", user)
    matching_stickers, fuzzy_matching_stickers, duration = get_matching_stickers(
        session, context
    )

    assert len(fuzzy_matching_stickers) == 0
    assert len(matching_stickers) == 50
    for i, result in enumerate(matching_stickers):
        # The stickers are firstly sorted by:
        # 1. score
        # 2. StickerSet.name
        # 3. Sticker.file_unique_id
        #
        # Thereby we expect the `a_dumb_shit` set first (20 results), since the scores are the same
        # for both sets, but this set's name is higher in order.
        if i < 20:
            assert result[1] == f"sticker_{i+40}"
            assert result[3] == "a_dumb_shit"
            assert result[4] == first_score
        # Next we get the second set in order of the file_unique_ids
        elif i >= 20:
            # We need to subtract 21, since we now start to count file_unqiue_ids from 0
            i = i - 20
            # Also do this little workaround to prevent fucky number sorting here as well
            if i < 10:
                i = f"0{i}"
            assert result[1] == f"sticker_{i}"
            assert result[3] == "z_mega_awesome"
            assert result[4] == second_score

    # Context properties have not been changed
    assert not context.switched_to_fuzzy
    assert context.limit is None
    assert context.fuzzy_offset is None


def test_strict_sticker_search_set_score(
    session, tg_context, strict_inline_search, user
):
    """Test correct score calculation for sticker set titles."""
    # Simple search which should get nearly all stickers from both sets
    context = Context(tg_context, "awesome", "", user)
    matching_stickers, fuzzy_matching_stickers, duration = get_matching_stickers(
        session, context
    )
    assert len(matching_stickers) == 40
    assert len(fuzzy_matching_stickers) == 0
    for i, result in enumerate(matching_stickers):
        # Also do this little workaround to prevent fucky number sorting here as well
        if i < 10:
            i = f"0{i}"
        assert result[1] == f"sticker_{i}"
        assert result[3] == "z_mega_awesome"
        assert result[4] == 0.75


def test_no_combined_on_full_strict(session, tg_context, strict_inline_search, user):
    """Test fuzzy search for stickers."""
    context = Context(tg_context, "roflcpter unique-other", "", user)
    # Add ten more stickers to the strict matching set
    sticker_set = strict_inline_search[0]
    for i in range(60, 70):
        sticker = sticker_factory(session, f"sticker_{i}", ["testtag", "unique-other"])
        sticker_set.stickers.append(sticker)
    session.commit()

    matching_stickers, fuzzy_matching_stickers, duration = get_matching_stickers(
        session, context
    )

    # Context properties have been properly set
    assert not context.switched_to_fuzzy
    assert context.limit is None
    assert context.fuzzy_offset is None

    # Sticker result counts are correct
    assert len(matching_stickers) == 50
    assert len(fuzzy_matching_stickers) == 0


def test_nsfw_search(session, tg_context, strict_inline_search, user):
    """Test nsfw search for stickers."""
    context = Context(tg_context, "nsfw porn roflcopter", "", user)

    sticker_set = strict_inline_search[0]
    sticker_set.nsfw = True

    # Add specific sticker to tag
    sticker = sticker_set.stickers[0]
    tag = Tag.get_or_create(session, "porn", False, False)
    sticker.tags.append(tag)
    session.commit()

    matching_stickers, fuzzy_matching_stickers, duration = get_matching_stickers(
        session, context
    )
    assert len(matching_stickers) == 1
    assert matching_stickers[0][1] == sticker.file_id
