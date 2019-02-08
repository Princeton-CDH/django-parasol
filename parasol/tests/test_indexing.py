from unittest.mock import patch, Mock, MagicMock

import pytest

try:
    from django.db.models.query import QuerySet
except ImportError:
    QuerySet = None

from parasol.indexing import Indexable
from parasol.tests.utils import skipif_no_django


# DefineIndexable subclasses for testing

class SimpleIndexable(Indexable):
    """simple indexable subclass"""
    id = 'a'

    def index_item_type(self):
        return 'thing'


class ModelIndexable(Indexable):
    """mock-model indexable subclass"""
    id = 1

    class _meta:
        verbose_name = 'model'


@skipif_no_django
@patch('parasol.indexing.SolrClient')
class TestIndexable:

    def test_all_indexables(self, mocksolr):
        indexables = Indexable.all_indexables()
        assert SimpleIndexable in indexables
        assert ModelIndexable in indexables

    def test_index_item_type(self, mocksolr):
        # use model verbose name by default
        assert ModelIndexable().index_item_type() == 'model'

    def test_index_id(self, mocksolr):
        assert SimpleIndexable().index_id() == 'thing.a'
        assert ModelIndexable().index_id() == 'model.1'

    def test_index_data(self, mocksolr):
        model = ModelIndexable()
        data = model.index_data()
        assert data['id'] == model.index_id()
        assert data['item_type'] == model.index_item_type()
        assert len(data) == 2

    def test_index(self, mocksolr):
        # index method on a single object instance
        model = ModelIndexable()
        model.index()
        # NOTE: because solr is stored on the class,
        # mocksolr.return_value is not the same object
        model.solr.update.index.assert_called_with([model.index_data()])

    def test_remove_from_index(self, mocksolr):
        # remove from index method on a single object instance
        model = ModelIndexable()
        model.remove_from_index()
        model.solr.update.delete_by_id.assert_called_with([model.index_id()])

    def test_index_items(self, mocksolr):
        items = [SimpleIndexable() for i in range(10)]

        indexed = Indexable.index_items(items)
        assert indexed == len(items)
        Indexable.solr.update.index \
            .assert_called_with([i.index_data() for i in items])

        # index in chunks
        Indexable.index_chunk_size = 6
        Indexable.solr.reset_mock()
        indexed = Indexable.index_items(items)
        assert indexed == len(items)
        # first chunk
        Indexable.solr.update.index \
            .assert_any_call([i.index_data() for i in items[:6]])
        # second chunk
        Indexable.solr.update.index \
            .assert_any_call([i.index_data() for i in items[6:]])

        # pass in a progressbar object
        mock_progbar = Mock()
        Indexable.index_items(items, progbar=mock_progbar)
        # progress bar update method should be called once for each chunk
        assert mock_progbar.update.call_count == 2

    def test_index_items__queryset(self, mocksolr):
        # index a queryset
        mockqueryset = MagicMock(spec=QuerySet)
        Indexable.index_items(mockqueryset)
        mockqueryset.iterator.assert_called_with()
