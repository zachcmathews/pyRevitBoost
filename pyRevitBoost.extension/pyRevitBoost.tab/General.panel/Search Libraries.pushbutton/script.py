# pylint: disable=import-error
import clr
clr.AddReference('System.ObjectModel')
from System.Collections.ObjectModel import ObservableCollection

clr.AddReference('System.Collections')
from System.Collections.Generic import List

import os
import sys
import re
import json
from itertools import groupby

from Autodesk.Revit.DB import ElementId, ElementTransformUtils
from Autodesk.Revit.Exceptions import (ArgumentException,
                                       InvalidOperationException)

import rpw
from pyrevit import forms, script

__doc__ = '''\
Find a family type or view in the libraries and insert it into the document.
'''
__title__ = 'Search\nLibraries'
__author__ = 'Zachary Mathews'


class TrieNode:
    def __init__(self):
        self.children = [None] * (26 + 10)
        self.terminal_items = []
        self.items = []


class Trie:
    def __init__(self):
        self.root = self.create_node()

    def create_node(self):
        return TrieNode()

    def _char_to_index(self, ch):
        if ch.isalpha():
            return ord(ch) - ord('a')
        elif ch.isdigit():
            return ord(ch) - ord('0') + 26

    def insert(self, key, item):
        p_crawl = self.root
        for char in key:
            p_crawl.items.append(item)

            index = self._char_to_index(char)
            if not p_crawl.children[index]:
                p_crawl.children[index] = self.create_node()

            p_crawl = p_crawl.children[index]

        p_crawl.terminal_items.append(item)

    def search(self, key):
        p_crawl = self.root

        # Add a point to each item for each additional character in one
        # of its keywords that matches the search term
        for char in key:
            index = self._char_to_index(char)
            if not p_crawl.children[index]:
                break

            for item in p_crawl.items:
                item.score += 1

            p_crawl = p_crawl.children[index]
        else:
            # Add an extra 2 points to each item with the whole search term
            # in its keywords list
            for item in p_crawl.terminal_items:
                item.score += 5


class ScoredTemplateListItem(forms.TemplateListItem):
    def __init__(self, *args, **kwargs):
        super(ScoredTemplateListItem, self).__init__(*args, **kwargs)
        self._score = 0

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, score):
        self._score = score


class FuzzySelectFromList(forms.SelectFromList):
    def __init__(self, *args, **kwargs):
        super(FuzzySelectFromList, self).__init__(*args, **kwargs)

        self.index = dict()
        for item in self._get_active_ctx():
            name = ''.join(
                [c for c in item.name.lower() if c.isalnum() or c.isspace()]
            )
            terms = set([t for t in name.split()])

            for term in terms:
                if not term[0] in self.index.keys():
                    self.index[term[0]] = Trie()

                self.index[term[0]].insert(term, item)

    # Override
    def search_txt_changed(self, sender, args):
        '''Handle text change in search box.'''
        if self.search_tb.Text == '':
            self.hide_element(self.clrsearch_b)
        else:
            self.show_element(self.clrsearch_b)

        self._search = self.search_tb.Text
        if self._search:
            self._compute_scores()
            self._list_options(option_filter=self.search_tb.Text)

    # Override
    def _list_options(self, option_filter=None):
        self.checkall_b.Content = 'Check'
        self.uncheckall_b.Content = 'Uncheck'
        self.toggleall_b.Content = 'Toggle'

        # Display top 15 matches
        items = set(self._get_active_ctx())
        top_matches = []
        while items is not None and len(top_matches) < 15:
            top_match = max(items, key=lambda item: item.score)
            top_matches.append(top_match)
            items.remove(top_match)

        self.list_lb.ItemsSource = \
            ObservableCollection[forms.TemplateListItem](
                [m for m in top_matches]
            )

    def _compute_scores(self):
        for item in self._get_active_ctx():
            item.score = 0

        search_phrase = ''.join(
            [c for c in self._search.lower() if c.isalnum() or c.isspace()]
        )
        search_terms = set([term for term in search_phrase.split()])
        for term in search_terms:
            if term[0] in self.index.keys():
                self.index[term[0]].search(term)


def _insert_view(db):
    class View(object):
        def __init__(self, path, name):
            self._path = path
            self._name = name

        @property
        def name(self):
            return self._name

        @property
        def path(self):
            return self._path

    class ViewOption(ScoredTemplateListItem):
        @property
        def name(self):
            return '{}'.format(self.item.name)

    views = []
    for path, _views in db["views"].items():
        for view in _views:
            views.append(View(path=path, name=view))

    options = []
    for view in views:
        options.append(ViewOption(view))

    res = FuzzySelectFromList.show(
        context=options,
        multiselect=True
    )

    if not res:
        sys.exit()

    succeeded = []
    failed = []
    for path, views in groupby(res, key=lambda view: view.path):
        doc = rpw.revit.doc
        try:
            other_doc = \
                rpw.revit.app.OpenDocumentFile(path)
        except:
            failed.extend([v.name for v in views])
        else:
            other_doc_views = rpw.db.Collector(
                doc=other_doc,
                of_category='OST_Views'
            ).get_elements(wrapped=False)

            view_names = set([v.name for v in views])
            views_to_copy = List[ElementId]([
                v.Id for v in other_doc_views if v.Name in view_names
            ])

            with rpw.db.Transaction(
                doc=doc, 
                name='Load views from {}'.format(path)
            ):
                try:
                    copied_views = ElementTransformUtils.CopyElements(
                        other_doc,
                        views_to_copy,
                        doc,
                        None,
                        None
                    )
                except (ArgumentException, InvalidOperationException):
                    failed.extend(view_names)
                else:
                    for view in copied_views:
                        view_names.remove(doc.GetElement(view).Name)
                        succeeded.append(doc.GetElement(view).Name)

                    failed.extend(view_names)

            other_doc.Close(False)

    if failed:
        forms.alert(
            msg='Successfully loaded the following views:\n{}\n\n'
                'Failed to load the following views:\n{}'.format(
                    '\n'.join(succeeded),
                    '\n'.join(failed)
                ),
            exitscript=True
        )


def _insert_family_type(db):
    class FamilyType(object):
        def __init__(self, path, name):
            self._path = path
            self._name = name

        @property
        def name(self):
            return self._name

        @property
        def path(self):
            return self._path

    class FamilyTypeOption(ScoredTemplateListItem):
        @property
        def name(self):
            return '{}'.format(self.item.name)

    family_types = []
    for path, _family_types in db["family_types"].items():
        for family_type in _family_types:
            family_types.append(FamilyType(path=path, name=family_type))

    options = []
    for family_type in family_types:
        options.append(FamilyTypeOption(family_type))

    res = FuzzySelectFromList.show(
        context=options,
        multiselect=True
    )

    if not res:
        sys.exit()

    succeeded = []
    failed = []
    for ft in res:
        with rpw.db.Transaction(
            doc=rpw.revit.doc,
            name='Load family type {}'.format(ft.name)
        ):
            if rpw.revit.doc.LoadFamilySymbol(ft.path, ft.name):
                succeeded.append(ft.name)
            else:
                failed.append(ft.name)

    if failed:
        forms.alert(
            msg='Successfully loaded the following family types:\n{}\n\n'
                'Failed to load the following family types:\n{}'.format(
                    '\n'.join(succeeded),
                    '\n'.join(failed)
                ),
            exitscript=True
        )


def _index_libraries():
    def _is_new(file, last_updated):
        return os.path.getctime(file) > last_updated

    def _is_updated(file, last_updated):
        return os.path.getmtime(file) > last_updated

    def _is_not_old(filename):
        old_regex = r'^.+\.old$'
        return not re.match(old_regex, filename)

    def _is_not_revision(filename):
        revision_regex = r'^.+\.[0-9]{4,}$'
        return not re.match(revision_regex, filename)

    app = rpw.revit.app
    libraries_db = script.get_data_file('boost_libraries_db', 'json')
    last_updated = None
    if os.path.isfile(libraries_db):
        last_updated = os.path.getmtime(libraries_db)
        with open(libraries_db, 'r') as f:
            libraries = json.load(f)

            if 'views' not in libraries.keys():
                libraries['views'] = {}
            if 'family_types' not in libraries.keys():
                libraries['family_types'] = {}
    else:
        user_wishes_to_proceed = forms.alert(
            msg='This might take a while. Are you sure you want to continue?',
            ok=False,
            yes=True,
            no=True
        )
        if not user_wishes_to_proceed:
            sys.exit()

        libraries = {}
        libraries['views'] = {}
        libraries['family_types'] = {}

    libs = [lib.Value for lib in app.GetLibraryPaths()]
    rvts = []
    rfas = []
    for lib in libs:
        for root, _, files in os.walk(lib):
            for file in files:
                filename, file_ext = os.path.splitext(file)

                if (
                    _is_not_revision(filename)
                    and _is_not_old(filename)
                    and (
                        _is_new(os.path.join(root, file), last_updated)
                        or _is_updated(os.path.join(root, file), last_updated)
                        or last_updated is None
                    )
                ):
                    if file_ext == '.rvt':
                        rvts.append(os.path.join(root, file))
                    elif file_ext == '.rfa':
                        rfas.append(os.path.join(root, file))

    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        count = 0
        total = len(rvts) + len(rfas)

        # Remove files that no longer exist from library
        old_views_by_rvt = libraries['views']
        for rvt in old_views_by_rvt.keys():
            if not os.path.isfile(rvt):
                del libraries['views'][rvt]

        old_family_types_by_rfa = libraries['family_types']
        for rfa in old_family_types_by_rfa.keys():
            if not os.path.isfile(rfa):
                del libraries['family_types'][rfa]

        # Gather information on changed rvt files
        views_by_rvt = {}
        for rvt in rvts:
            if pb.cancelled:
                sys.exit()

            if rvt == rpw.revit.doc.PathName:
                doc = rpw.revit.doc
                is_active_doc = True
            else:
                doc = app.OpenDocumentFile(rvt)
                is_active_doc = False

            views = rpw.db.Collector(
                doc=doc,
                of_category='OST_Views'
            )

            views_by_rvt[rvt] = [v.Name for v in views]

            if not is_active_doc:
                doc.Close(False)

            count += 1
            pb.update_progress(count, total)

        # Gather information on changed rfa files
        family_types_by_rfa = {}
        for rfa in rfas:
            if pb.cancelled:
                sys.exit()

            if rvt == rpw.revit.doc.PathName:
                doc = rpw.revit.doc
                is_active_doc = True
            else:
                doc = app.OpenDocumentFile(rfa)
                is_active_doc = False

            fm = doc.FamilyManager

            family_types_by_rfa[rfa] = [t.Name for t in fm.Types]

            if not is_active_doc:
                doc.Close(False)

            count += 1
            pb.update_progress(count, total)

        # Update library with new information
        libraries['views'].update(views_by_rvt)
        libraries['family_types'].update(family_types_by_rfa)

        # Write library index to file
        data = json.dumps({
            "views": libraries['views'],
            "family_types": libraries['family_types']
        })
        with open(libraries_db, 'w+') as f:
            f.write(data)


def _get_libraries():
    libraries_db = script.get_data_file('boost_libraries_db', 'json')
    if not os.path.isfile(libraries_db):
        forms.alert(
            msg='Sorry! It appears that your Revit libraries have not been '
                'indexed yet. '
                'Please ensure that your Revit library paths are properly '
                'configured, and then choose Index Libraries to index the '
                'libraries.',
            ok=False,
            cancel=True,
            exitscript=True
        )

    with open(libraries_db, 'r') as f:
        libraries = json.load(f)

    return libraries


if __name__ == '__main__':
    cmd = forms.CommandSwitchWindow.show(
        context=['Insert View', 'Insert Family Type', 'Index Libraries']
    )

    if cmd == 'Insert View':
        libraries = _get_libraries()
        _insert_view(libraries)
    elif cmd == 'Insert Family Type':
        libraries = _get_libraries()
        _insert_family_type(libraries)
    elif cmd == 'Index Libraries':
        _index_libraries()
