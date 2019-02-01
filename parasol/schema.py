'''
Solr schema configuration and management


'''
import logging

from attrdict import AttrDefault


logger = logging.getLogger(__name__)


class SolrField:
    """A descriptor for declaring a solr field on a :class:`SolrSchema`
    instance.
    """

    def __init__(self, fieldtype, required=False, multivalued=False):
        self.type = fieldtype
        self.required = required
        self.multivalued = multivalued

    def __get__(self, obj, objtype):
        return {'type': self.type, 'required': self.required,
                'multiValued': self.multivalued}

    def __set__(self, obj, val):
        # enforce read-only descriptor
        raise AttributeError


class SolrTypedField(SolrField):
    '''Base class for typed solr field descriptor. For use with your own
    field types, extend and set :attr:`field_type`.'''
    field_type = None

    def __init__(self, *args, **kwargs):
        super().__init__(self.field_type, *args, **kwargs)


class SolrStringField(SolrTypedField):
    '''Solr string field'''
    field_type = 'string'


class SolrAnalyzer:

    tokenizer = None
    filters = None

    @classmethod
    def as_solr_config(cls):
        return {
            'tokenizer': {
                'class': cls.tokenizer
            },
            'filters': cls.filters
        }


class SolrFieldType:
    """A descriptor for declaring and configure a solr field type on
    a :class:`SolrSchema`instance.
    """
    def __init__(self, field_class, analyzer):
        self.field_class = field_class
        self.analyzer = analyzer

    def __get__(self, obj, objtype):
        return {
            'class': self.field_class,
            'analyzer': self.analyzer.as_solr_config()
        }

    def __set__(self, obj, val):
        # enforce read-only descriptor
        raise AttributeError


class SolrSchema:
    '''Solr schema configuration'''

    @classmethod
    def get_configuration(cls):
        '''Find a SolrSchema subclass for use as schema configuration.
        Currently only supports one schema configuration.'''
        subclasses = cls.__subclasses__()
        if not subclasses:
            raise Exception('No Solr schema configuration found')
        elif len(subclasses) > 1:
            raise Exception('Currently only one Solr schema configuration is supported (found %d)' \
                             % len(subclasses))

        return subclasses[0]

    @classmethod
    def get_field_names(cls):
        '''iterate over class attributes and return all that are instances of
        :class:`SolrField`'''
        return [attr_name for attr_name, attr_type in cls.__dict__.items()
                if isinstance(attr_type, SolrField)]

    @classmethod
    def get_field_types(cls):
        '''iterate over class attributes and return all that are instances of
        :class:`SolrFieldType`'''
        return [attr_name for attr_name, attr_type in cls.__dict__.items()
                if isinstance(attr_type, SolrFieldType)]

    @classmethod
    def configure_solr_fields(cls, solr):
        '''Update the configured Solr instance schema to match
        the configured fields.  Returns a tuple with the number of fields
        created and updated.'''

        current_fields = [field.name for field in solr.schema.list_fields()]
        configured_field_names = cls.get_field_names()

        # use attrdict instead of defaultdict since we have attrmap installed
        stats = AttrDefault(int, {})

        for field_name in configured_field_names:
            field_opts = getattr(cls, field_name)
            if field_name not in current_fields:
                logger.debug('Adding schema field %s %s', field_name, field_opts)
                solr.schema.add_field(name=field_name, **field_opts)
                stats.added += 1
            else:
                # NOTE: currently no check if field configuration has changed
                logger.debug('Replace schema field %s %s', field_name, field_opts)
                solr.schema.replace_field(name=field_name, **field_opts)
                stats.replaced += 1

        # remove previously defined fields that are no longer current
        for field_name in current_fields:
            # don't remove special fields!
            if field_name == 'id' or field_name.startswith('_'):
                continue
            if field_name not in configured_field_names:
                stats.deleted += 1
                logger.debug('Delete schema field %s', field_name)
                solr.schema.delete_field(field_name)

        return stats

    @classmethod
    def configure_solr_fieldtypes(cls, solr):
        '''Update the configured Solr instance so the schema includes
        the configured field types, if any.
        Returns a tuple with the number of fields
        created and updated.'''

        configured_field_types = cls.get_field_types()

        stats = AttrDefault(int, {})

        # if none are configured, nothing to do
        if not configured_field_types:
            return stats

        # convert list return into dictionary keyed on field type name
        current_field_types = {ftype['name']: ftype
                               for ftype in solr.schema.list_field_types()}

        for field_type in configured_field_types:
            field_type_opts = getattr(cls, field_type)
            # add name for comparison with current config
            field_type_opts['name'] = field_type
            if field_type in current_field_types:
                # remove name for comparing field type configuration
                current_field_type_opts = current_field_types[field_type]
                del current_field_type_opts['name']

                # if field exists but definition has changed, replace it
                stats.updated += 1
                logger.debug('Updating field type %s with options %s', field_type, field_type_opts)
                solr.schema.replace_field_type(**field_type_opts)

                # NOTE: could add logic to only update when the field type
                # configuration has changed, but simple dict comparison
                # does not recognize as equal even when the config has
                # not changed

            # otherwise, create as a new field type
            else:
                stats.added += 1
                logger.debug('Adding field type %s with options %s', field_type, field_type_opts)
                solr.schema.add_field_type(**field_type_opts)
                # self.solr.schema.create_field_type(self.solr_collection, field_type)

            # NOTE: currently no deletion support; would need to keep
            # a list of predefined Solr field types to check against,
            # which might change, so could be unreliable

        return stats