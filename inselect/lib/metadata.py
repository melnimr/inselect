"""Metadata field template
"""
from __future__ import print_function

import json
import re

from collections import Counter, namedtuple, OrderedDict
from functools import partial
from itertools import chain, count, ifilter, izip
from pathlib import Path

from .utils import debug_print, duplicated, FormatDefault

def _fields_from_template_spec(fields):
    "Validates fields and returns a list of processed fields"
    # Name field must be present
    if any('Name' not in f for f in fields):
        raise ValueError(u'One or more fields do not have a name')

    # No names should be duplicated
    field_names = [f['Name'] for f in fields]
    dup = duplicated(field_names)
    if dup:
        msg = u'Duplicated fields {0}'
        raise ValueError(msg.format(sorted(list(dup))))

    # Can't give both Choices and ChoicesWithData
    bad = next(ifilter(lambda f: 'Choices' in f and 'ChoicesWithData' in f, fields), None)
    if bad:
        msg = u'Both "Choices" and "ChoicesWithData" given for for [{0}]'
        raise ValueError(msg.format(bad['Name']))

    # Validate Choices
    for field in ifilter(lambda f: 'Choices' in f, fields):
        dup = duplicated(field['Choices'])
        if dup:
            # Labels in Choices must be unique
            msg = u'Duplicated "Choices" label for [{0}]: {1}'
            raise ValueError(msg.format(field['Name'], sorted(list(dup))))
        elif not field['Choices']:
            # No choices
            msg = u'Empty "Choices" for [{0}]'
            raise ValueError(msg.format(field['Name']))

    # Validate ChoicesWithData
    for field in ifilter(lambda f: 'ChoicesWithData' in f, fields):
        # A field named '{0}-value' will be synthesized for ChoicesWithData
        # fields
        value_field = '{0}-value'.format(field['Name'])
        if value_field in field_names:
            msg = u'A field named "{0}" cannot be defined'
            raise ValueError(msg.format(value_field))
        dup = duplicated(label for label, data in field['ChoicesWithData'])
        if dup:
            # Labels in ChoiceWithData must be unique
            msg = u'Duplicated "ChoicesWithData" label for [{0}]: {1}'
            raise ValueError(msg.format(field['Name'], sorted(list(dup))))
        elif not field['ChoicesWithData']:
            # No choices
            msg = u'Empty "ChoicesWithData" for [{0}]'
            raise ValueError(msg.format(field['Name']))

    for field in ifilter(lambda f: 'ChoicesWithData' in f, fields):
        field['ChoicesWithData'] = OrderedDict(field['ChoicesWithData'])

    return fields


class MetadataTemplate(object):
    """Metadata fields template
    """

    def __init__(self, spec):
        """spec - a dict that conforms for the metadata template spec.
        """

        fields = _fields_from_template_spec(spec.get('Fields', []))

        if not spec.get('Name'):
            raise ValueError('No template name')
        elif not fields:
            raise ValueError('No fields')

        self._name = spec['Name']

        if 'Cropped file suffix' in spec:
            try:
                suffix = Path('x').with_suffix(spec['Cropped file suffix']).suffix
            except ValueError, e:
                msg = u'Invalid cropped file suffix [{0}]'
                raise ValueError(msg.format(spec['Cropped file suffix']))
            else:
                self._cropped_image_suffix = suffix
        else:
            self._cropped_image_suffix = None

        self._fields = fields

        # A method that returns labels from metadata dicts
        self._format_label = partial(FormatDefault(default='').format,
                                     spec.get('Object label', '{catalogNumber}'))

        # Map from field name to field
        self._fields_mapping = {f['Name'] : f for f in fields}

        # Map from field name to field
        self._choices_with_data_mapping = {f['Name'] : f for f in fields if 'ChoicesWithData' in f}

        # Mapping from name to parse function, for those fields that have a parser
        self._parse_mapping = {k: v['Parser'] for k, v in self._fields_mapping.iteritems() if 'Parser' in v}

        # List of mandatory fields
        self._mandatory = [f['Name'] for f in self._fields if f.get('Mandatory')]

    def __repr__(self):
        msg = '<MetadataTemplate [{0}] with {1} fields>'
        return msg.format(self._name, len(self._fields))

    def __str__(self):
        msg = 'MetadataTemplate [{0}] with {1} fields'
        return msg.format(self._name, len(self._fields))

    @property
    def name(self):
        """The template's name
        """
        return self._name

    @property
    def fields(self):
        """A list of dicts
        """
        return self._fields

    def field_names(self):
        "A generator of metadata field names, including synthesized fields"
        for field in self._fields:
            yield field['Name']
            if 'ChoicesWithData' in field:
                yield u'{0}-value'.format(field['Name'])

    def box_metadata(self, box):
        "Returns a dict {field_name: value} for box"
        md = box['fields']

        # Names of fields that have an associated data
        c = self._choices_with_data_mapping
        for field in ifilter(lambda f: md.get(f['Name']) in f['ChoicesWithData'], c.itervalues()):
            value = field['ChoicesWithData'][md.get(field['Name'])]
            md[u'{0}-value'.format(field['Name'])] = value
        return md

    def format_label(self, box):
         "Returns a textual label of box"
         return self._format_label(**self.box_metadata(box))

    @property
    def cropped_image_suffix(self):
        "The suffix to use for cropped object images"
        return self._cropped_image_suffix

    @property
    def mandatory(self):
        """List of names of mandatory fields
        """
        return self._mandatory

    def validate_box(self, box):
        """Returns True if the box's metadata validates against this template;
        False if not
        """
        md = box['fields']

        # Mandatory fields
        if any(not md.get(f) for f in self.mandatory):
            return False
        try:
            parseable = ( (k, v) for k, v in self._parse_mapping.iteritems() if k in set(md.keys()))
            for field, parse in parseable:
                parse(md[field])
        except ValueError:
            return False
        else:
            return True

    def validate_field(self, field, value):
        """Returns True if field value validates against this template; False if
        not
        """
        if field not in self._fields_mapping:
            # A field that this template does not know about
            return True
        elif not value and field in self.mandatory:
            # Field is mandatory and no value was provided
            return False
        elif value:
            # Attempt to parse the value
            parse = self._parse_mapping.get(field)
            if parse:
                try:
                    debug_print('Parse [{0}] [{1}]'.format(field, value))
                    parse(value)
                except ValueError:
                    # Could not be parsed
                    debug_print('Failed parse [{0}] [{1}]'.format(field, value))
                    return False

        # The value is valid
        return True

    def visit_document(self, document, visitor):
        visitor.begin_visit(document)
        self._visit_boxes(document, visitor)
        self._visit_labels(document, visitor)
        visitor.end_visit(document)

    def _visit_boxes(self, document, visitor):
        for index, box in enumerate(document.items):
            self._visit_box(visitor, index, box)

    def _visit_box(self, visitor, index, box):
        box_label = self.format_label(box)
        md = box['fields']
        for field in (f for f in self.mandatory if not md.get(f)):
            visitor.missing_mandatory(index, box_label, field)

        for field, parse in ( (k, v) for k, v in self._parse_mapping.iteritems() if k in set(md.keys())):
            try:
                parse(md[field])
            except ValueError:
                visitor.failed_parse(index, box_label, field)

    def _visit_labels(self, document, visitor):
        """Visit the document
        """
        labels = [self.format_label(box) for box in document.items]

        # Labels must be given
        for index in (i for i, l in izip(count(), labels) if not l):
            visitor.missing_label(index)

        # Non-missing object labels must be unique
        counts = Counter(labels)
        for label in (v for v, n in counts.iteritems() if v and n > 1):
            visitor.duplicated_labels(label)


class MetadataVisitor(object):
    def begin_visit(self, document):
        pass

    def missing_mandatory(self, index, label, field):
        pass

    def failed_parse(self, index, label, field):
        pass

    def missing_label(self, index):
        pass

    def duplicated_labels(self, label):
        pass

    def end_visit(self, document):
        pass


class PrintVisitor(MetadataVisitor):
    def begin_visit(self, document):
        print('begin_visit', document)

    def missing_mandatory(self, index, label, field):
        print('missing_mandatory', box, field)

    def failed_parse(self, index, label, field):
        print('failed_parse', box, field)

    def missing_label(self, index):
        print('missing_label', index)

    def duplicated_labels(self, label):
        print('duplicated_labels', label)

    def end_visit(self, document):
        print('end_visit', document)


MissingMandatory = namedtuple('MissingMandatory', ['index', 'label', 'field'])
FailedParse = namedtuple('FailedParse', ['index', 'label', 'field'])

class CollectVisitor(MetadataVisitor):
    """Collects validation problems
    """
    def begin_visit(self, document):
        self._missing_mandatory = []
        self._failed_parse = []
        self._missing_label = []
        self._duplicated_labels = []

    def missing_mandatory(self, index, label, field):
        self._missing_mandatory.append(MissingMandatory(index, label, field))

    def failed_parse(self, index, label, field):
        self._failed_parse.append(FailedParse(field, index, label))

    def missing_label(self, index):
        self._missing_label.append(index)

    def duplicated_labels(self, label):
        self._duplicated_labels.append(label)

    def all_problems(self):
        return ValidationProblems(self._missing_mandatory, self._failed_parse,
                                  self._missing_label, self._duplicated_labels)


class ValidationProblems(object):
    """A container of validation problems
    """
    def __init__(self, missing_mandatory, failed_parse, missing_label,
                 duplicated_labels):
        self.missing_mandatory = missing_mandatory
        self.failed_parse = failed_parse
        self.missing_label = missing_label
        self.duplicated_labels = duplicated_labels

    @property
    def any_problems(self):
        return bool(self.missing_mandatory or
                    self.failed_parse or
                    self.missing_label or
                    self.duplicated_labels)