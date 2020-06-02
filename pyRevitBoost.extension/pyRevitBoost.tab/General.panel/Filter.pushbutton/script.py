import clr
clr.AddReference('System.Core')
from System.Dynamic import ExpandoObject

from System.Collections.Generic import List
from Autodesk.Revit.DB import BuiltInParameter, ElementId

from pyrevit import script, forms
import rpw

__doc__ = '''Filter based on lower taxonomies.'''
__title__ = 'Filter'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'

class FilterForm(forms.WPFWindow):
    def __init__(self, xaml):
        forms.WPFWindow.__init__(self, xaml)

        global categories, families, types, worksets
        self.categories = []
        for category in categories:
            _ = ExpandoObject()
            _.name = category
            _.selected = False
            _.remains = True
            self.categories.append(_)
        self.families = []
        for family in families:
            _ = ExpandoObject()
            _.name = family
            _.selected = False
            _.remains = True
            self.families.append(_)
        self.types = []
        for type in types:
            _ = ExpandoObject()
            _.name = type
            _.selected = False
            _.remains = True
            self.types.append(_)
        self.worksets = []
        for workset in worksets:
            _ = ExpandoObject()
            _.name = workset
            _.selected = False
            _.remains = True
            self.worksets.append(_)

        self.FindName('categoriesListBox').ItemsSource = self.categories
        self.FindName('familiesListBox').ItemsSource = self.families
        self.FindName('typesListBox').ItemsSource = self.types
        self.FindName('worksetsListBox').ItemsSource = self.worksets

        self.filteredElements = elements
        self.clickedAccept = False

    def apply(self, sender, args):
        global elements

        # Collect selected filter criteria
        selectedCategories = [category.name for category in self.categories if category.selected and category.remains]
        selectedFamilies = [family.name for family in self.families if family.selected and family.remains]
        selectedTypes = [type.name for type in self.types if type.selected and type.remains]
        selectedWorksets = [workset.name for workset in self.worksets if workset.selected and workset.remains]

        # If any are empty, dont filter based on that criterion
        selectedCategories = [category.name for category in self.categories if category.remains] if not selectedCategories else selectedCategories
        selectedFamilies = [family.name for family in self.families if family.remains] if not selectedFamilies else selectedFamilies
        selectedTypes = [type.name for type in self.types if type.remains] if not selectedTypes else selectedTypes
        selectedWorksets = [workset.name for workset in self.worksets if workset.remains] if not selectedWorksets else selectedWorksets

        # Compute results of filtering based on new criteria
        self.filteredElements = [
            element for element in elements
            if element.Category.Name in selectedCategories
            and element.get_Parameter(BuiltInParameter.ELEM_FAMILY_PARAM).AsValueString() in selectedFamilies
            and element.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString() in selectedTypes
            and worksetTable.GetWorkset(element.WorksetId).Name in selectedWorksets
        ]

        # Compute remaining filterable criteria
        remainingCategories = set([element.Category.Name for element in self.filteredElements])
        remainingFamilies = set([element.get_Parameter(BuiltInParameter.ELEM_FAMILY_PARAM).AsValueString() for element in self.filteredElements])
        remainingTypes = set([element.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString() for element in self.filteredElements])
        remainingWorksets = set([worksetTable.GetWorkset(element.WorksetId).Name for element in self.filteredElements])
        for category in self.categories:
            if category.name not in remainingCategories:
                category.remains = False
        for family in self.families:
            if family.name not in remainingFamilies:
                family.remains = False
        for type in self.types:
            if type.name not in remainingTypes:
                type.remains = False
        for workset in self.worksets:
            if workset.name not in remainingWorksets:
                workset.remains = False
    def clear(self, sender, args):
        if self.tab == 'categoriesTab':
            for category in self.categories:
                category.selected = False
                category.remains = True
            for family in self.families:
                family.selected = False
                family.remains = True
            for type in self.types:
                type.selected = False
                type.remains = True
            for workset in self.worksets:
                workset.remains = True
        if self.tab == 'familiesTab':
            for category in self.categories:
                category.remains = True
            for family in self.families:
                family.selected = False
                family.remains = True
            for type in self.types:
                type.selected = False
                type.remains = True
            for workset in self.worksets:
                workset.remains = True
        if self.tab == 'typesTab':
            for category in self.categories:
                category.remains = True
            for family in self.families:
                family.remains = True
            for type in self.types:
                type.selected = False
                type.remains = True
            for workset in self.worksets:
                workset.remains = True
        if self.tab == 'worksetsTab':
            for category in self.categories:
                category.remains = True
            for family in self.families:
                family.remains = True
            for type in self.types:
                type.remains = True
            for workset in self.worksets:
                workset.selected = False
                workset.remains = True

        self.apply(sender, args)
    def clearAll(self, sender, args):
        for category in self.categories:
            category.selected = False
            category.remains = True
        for family in self.families:
            family.selected = False
            family.remains = True
        for type in self.types:
            type.selected = False
            type.remains = True
        for workset in self.worksets:
            workset.selected = False
            workset.remains = True

        self.apply(sender, args)

    def accept(self, sender, args):
        self.clickedAccept = True
        self.Close()
    def cancel(self, sender, args):
        self.Close()
    def exit(self, sender, args):
        if self.clickedAccept:
            self.apply(sender, args)
        else:
			self.clearAll(sender, args)

    def onTabChange(self, sender, args):
        self.apply(sender, args)
        self.tab = sender.SelectedValue.Name
    def show_dialog(self):
        self.ShowDialog()
        return self.filteredElements

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc
worksetTable = doc.GetWorksetTable()

elements = [doc.GetElement(id) for id in uidoc.Selection.GetElementIds()]
elements = [
    element for element in elements
    if element.Category
    and element.get_Parameter(BuiltInParameter.ELEM_FAMILY_PARAM)
    and element.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM)
    and element.WorksetId
]
if elements:
    # Compute filterable parameter values
    categories = sorted(set([element.Category.Name for element in elements]))
    families = sorted(set([element.get_Parameter(BuiltInParameter.ELEM_FAMILY_PARAM).AsValueString() for element in elements]))
    types = sorted(set([element.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString() for element in elements]))
    worksets = sorted(set([worksetTable.GetWorkset(element.WorksetId).Name for element in elements]))

    # Show form
    filteredElements = FilterForm('FilterForm.xaml').show_dialog()
    uidoc.Selection.SetElementIds(List[ElementId]([element.Id for element in filteredElements]))
