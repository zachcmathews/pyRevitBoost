from System.ComponentModel import (INotifyPropertyChanged,
                                   PropertyChangedEventArgs)
from Autodesk.Revit.DB import BuiltInParameter
from pyrevit import forms


class Option(INotifyPropertyChanged):
    def __init__(
        self, value, _filter, criterion,
        checked=False, available=True
    ):
        self._value = value
        self._filter = _filter
        self._criterion = criterion
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
    def quantity(self):
        return len(
            self._filter.passes(criterion=self._criterion, value=self._value)
        )

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

    def check_all(self):
        for o in self.options:
            if o.available:
                o.checked = True

    def uncheck_all(self):
        for o in self.options:
            if o.available:
                o.checked = False

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
        self._elements = elements
        self._filtered = elements

        self._criteria = []
        for c in criteria:
            option_values = sorted(set(e.get(c, 'None') for e in elements))
            self._criteria.append(Criterion(
                name=c,
                options=[
                    Option(v, _filter=self, criterion=c)
                    for v in option_values
                ]
            ))

    @property
    def criteria(self):
        return self._criteria

    @property
    def results(self):
        return self._filtered

    def passes(self, criterion, value):
        return [
            e for e in self._filtered
            if e.get(criterion, 'None') == value
        ]

    def apply(self):
        filtered = []
        for el in self._elements:
            for criterion in self._criteria:
                if not criterion.passes(el):
                    break
            else:
                filtered.append(el)

        self._filtered = filtered
        self._recompute_availability()

    def check_all(self, criterion):
        criterion.check_all()

    def uncheck_all(self, criterion):
        criterion.uncheck_all()

    def clear(self, criterion):
        criterion.clear()
        self.apply()
        self._recompute_availability()

    def clear_all(self):
        for criterion in self._criteria:
            criterion.clear()

        self._filtered = self._elements
        self._recompute_availability()

    def _recompute_availability(self):
        for criterion in self._criteria:
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

    def check_all(self, *args):
        self._filter.check_all(criterion=self._tab.criterion)

    def uncheck_all(self, *args):
        self._filter.uncheck_all(criterion=self._tab.criterion)

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


def get_element_meta(e, workset_table):
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