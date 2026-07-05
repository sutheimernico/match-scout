import pytest

from matchscout.ml.validation import purged_walk_forward_splits


def test_train_always_precedes_test():
    for train, test in purged_walk_forward_splits(120, n_splits=5):
        assert train.max() < test.min()


def test_no_overlap():
    for train, test in purged_walk_forward_splits(120, n_splits=5):
        assert set(train.tolist()).isdisjoint(test.tolist())


def test_embargo_gap_respected():
    embargo = 5
    for train, test in purged_walk_forward_splits(120, n_splits=5, embargo=embargo):
        assert test.min() - train.max() - 1 >= embargo


def test_expanding_window():
    sizes = [len(train) for train, _ in purged_walk_forward_splits(120, n_splits=5)]
    assert sizes == sorted(sizes)  # training window grows each fold


def test_covers_folds():
    splits = list(purged_walk_forward_splits(120, n_splits=5))
    assert len(splits) == 5


def test_too_few_samples_raises():
    with pytest.raises(ValueError, match="too few samples"):
        list(purged_walk_forward_splits(3, n_splits=5))


def test_bad_n_splits_raises():
    with pytest.raises(ValueError, match="n_splits"):
        list(purged_walk_forward_splits(120, n_splits=0))
