# pylint: disable=import-error
from functools import partial
from System.ComponentModel import (INotifyPropertyChanged,
                                   PropertyChangedEventArgs)
from Autodesk.Revit.DB import BuiltInParameter

import rpw
from pyrevit import forms

__doc__ = '''\
Filter based on category, family, type and workset.

Shift+Click = Filter based on user-selected parameters.
'''
__title__ = 'Filter'
__author__ = 'Zachary Mathews'


class Option(INotifyPropertyChanged):
    def __init__(self, value, checked=False, available=True):
        self._value = value
        self._checked = checked
        self._available = available
        self._property_changed_handlers = []

    def _raise_property_changed(self, property_name):
        args = PropertyChangedEventArgs(property_name)
        for handler in self._property_changed_handlers:
            handler(self, args)

    def add_PropertyChanged(self, handler):
        self._property_changed_handlers.append(handler)

    def remove_PropertyChanged(self, handler):
        self._property_changed_handlers.remove(handler)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self._raise_property_changed('value')

    @property
    def checked(self):
        return self._checked

    @checked.setter
    def checked(self, checked):
        self._checked = checked
        self._raise_property_changed('checked')

    @property
    def available(self):
        return self._available

    @available.setter
    def available(self, available):
        self._available = available
        self._raise_property_changed('available')


class Criterion(object):
    def __init__(self, name, options):
        self.name = name
        self.options = options

    def clear(self):
        for option in self.options:
            option.checked = False

    def passes(self, element):
        is_checked = any([
            o.checked for o in self.options
            if o.value == element.get(self.name, 'None')
        ])
        none_checked = not any(o.checked for o in self.options)
        return is_checked or none_checked


class Filter(object):
    def __init__(self, criteria, elements):
        self.criteria = criteria
        self._elements = elements
        self._filtered = elements

    @property
    def results(self):
        return self._filtered

    def apply(self):
        filtered = []
        for el in self._elements:
            for criterion in self.criteria:
                if not criterion.passes(el):
                    break
            else:
                filtered.append(el)

        self._filtered = filtered
        self._recompute_availability()

    def clear(self, criterion):
        criterion.clear()
        self.apply()
        self._recompute_availability()

    def clear_all(self):
        for criterion in self.criteria:
            criterion.clear()

        self._filtered = self._elements
        self._recompute_availability()

    def _recompute_availability(self):
        for criterion in self.criteria:
            for option in criterion.options:
                if not any(
                    e.get(criterion.name, 'None') == option.value
                    for e in self._filtered
                ):
                    option.checked = False
                    option.available = False
                else:
                    option.available = True


class FilterFormTab(object):
    def __init__(self, title, criterion):
        self.title = title
        self.criterion = criterion


class FilterForm(forms.WPFWindow):
    def __init__(self, template, _filter, elements):
        forms.WPFWindow.__init__(self, template)
        self._filter = _filter

        # Create a tab for each criterion
        self.tabs = []
        for criterion in self._filter.criteria:
            tab = FilterFormTab(
                title=criterion.name,
                criterion=criterion
            )
            self.tabs.append(tab)

        # Fill in template
        self.FindName('tabs').ItemsSource = self.tabs

        self._tab = self.tabs[0]
        self._clicked_accept = False

    def apply(self, *args):
        any_checked_and_available = any(
            o.checked
            for o in self._tab.criterion.options
            if o.available
        )
        if any_checked_and_available:
            self._filter.apply()

    def clear(self, *args):
        self._filter.clear(criterion=self._tab.criterion)

    def clear_all(self, *args):
        self._filter.clear_all()

    def accept(self, *args):
        self.apply(*args)
        self.Close()

    def cancel(self, *args):
        self.clear_all(*args)
        self.Close()

    def on_tab_change(self, sender, *args):
        self.apply(*args)
        self._tab = sender.SelectedValue

    def show_dialog(self):
        self.ShowDialog()
        return self._filter.results


def _get_element_meta(e, workset_table):
    category = e.Category
    family = e.get_Parameter(BuiltInParameter.ELEM_FAMILY_PARAM)
    _type = e.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM)
    workset_id = e.WorksetId
    phase_created = e.get_Parameter(BuiltInParameter.PHASE_CREATED)
    phase_demolished = e.get_Parameter(BuiltInParameter.PHASE_DEMOLISHED)

    phase_created = 'None' if phase_created is None else phase_created
    phase_demolished = 'None' if phase_demolished is None else phase_demolished

    if (
        category is None
        or family is None
        or _type is None
        or workset_id is None
    ):
        return {}
    else:
        return {
            'ID': e.Id,
            'Category': category.Name,
            'Family': family.AsValueString(),
            'Type': _type.AsValueString(),
            'Workset': workset_table.GetWorkset(workset_id).Name,
            'Phase Created': phase_created.AsValueString(),
            'Phase Demolished': phase_demolished.AsValueString(),
        }


if __name__ == '__main__':
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    selection = rpw.ui.Selection(uidoc=uidoc)
    _get_element_meta = partial(
        _get_element_meta,
        workset_table=doc.GetWorksetTable()
    )

    elements = [
        _get_element_meta(e)
        for e in selection.get_elements(wrapped=False)
        if _get_element_meta(e)
    ]

    parameters = [
        'Category', 'Family', 'Type', 'Workset', 'Phase Created',
        'Phase Demolished'
    ]
    criteria = []
    for p in parameters:
        option_values = sorted(set(e.get(p, 'None') for e in elements))
        criteria.append(Criterion(
            name=p,
            options=[Option(v) for v in option_values]
        ))

    if elements:
        _filter = Filter(criteria, elements)

        # Show form
        filtered_elements = FilterForm(
            template='FilterForm.xaml',
            _filter=_filter,
            elements=elements
        ).show_dialog()

        # Update selection
        selection.clear()
        selection.add([e['ID'] for e in filtered_elements])
        selection.update()
