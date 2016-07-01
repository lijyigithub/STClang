# -*- coding:utf-8 -*-
import sublime, sublime_plugin
from .compiler import Projector
from .opener import *
from .clang.cindex import *
import os
import re


proj = None
func_on_load = None
outer = None
on_selection_view_in_right = None
on_clone_callback = None

def get_view_cur(view):
    line, column = view.rowcol(view.sel()[0].begin())
    return line+1, column+1


def get_view_file(view):
    file_name = view.file_name()
    if file_name is None:
        return ''
    file_name = os.path.normpath(file_name)
    file_name = os.path.normcase(file_name)
    return file_name


def location_to_pos(location):
    l = location.line
    c = location.column
    return l, c


class find_sym_panel():
    def __init__(self, window):
        self.panel = window.get_output_panel('find_sym_panel')
        self.panel.set_syntax_file('Packages/STClang/find_symbols.tmLanguage')
        self.panel.set_name('find_sym_panel')
        self.window = window
        window.run_command('show_panel', {'panel': 'output.find_sym_panel'})

    def add_file(self, filename):
        self.panel.run_command('append', {'characters': 'File: %s\n' % filename, 'force': True, 'scroll_to_end': False})

    def add_line(self, line, code_line):
        self.panel.run_command('append', {'characters': '%s\t%s\n' % (line, code_line), 'force': True, 'scroll_to_end': False})

    def show(self):
        self.panel.set_read_only(True)

class error_panel():
    def __init__(self, window):
        self.panel = window.get_output_panel('error_panel')
        self.panel.set_syntax_file('Packages/STClang/errors.tmLanguage')
        self.panel.set_name('error_panel')
        self.window = window
        window.run_command('show_panel', {'panel': 'output.error_panel'})

    def set_file(self, filename):
        self.panel.set_name('error_panel - ' + filename)

    def add_line(self, line):
        self.panel.run_command('append', {'characters': line + '\n', 'force': True, 'scroll_to_end': False})

    def show(self):
        self.panel.set_read_only(True)

    def hide(self):
        self.panel.run_command('hide_panel', {'cancel': True})



class SclangOpenprj(sublime_plugin.TextCommand):
    def run(self, edit):
        global func_on_load
        def on_load(self, view):
            file_name = get_view_file(view)
            opener = Opener.get_opener(file_name)
            if opener is not None:
                opener.open(file_name, view)
        func_on_load = on_load
        self.view.window().run_command('prompt_open_file')

class SclangFellowdef(sublime_plugin.TextCommand):
    def __init__(self, whatever):
        self.cked = False
        sublime_plugin.TextCommand.__init__(self, whatever)

    def run(self, edit):
        global on_selection_view_in_right
        global on_clone_callback
        def view_def_in_right(cur_file, line, column):
            if not isinstance(proj, Projector):
                return
            cur = proj.get_def_of(cur_file, line, column)
            if cur is None:
                return
            def_file = cur.location.file.name
            proj.get_def_body_of(cur_file, line, column)
            return
            l, c = location_to_pos(cur.location)
            # for v in sublime.active_window().views_in_group(0):
            #     if os.path.samefile(v.file_name(), def_file):
            #         def clone_and_view(view):
            #             sublime.active_window().set_view_index(view, 1, 0)
            #             view.show_at_center(view.text_point(l, c))
            #         on_clone_callback = clone_and_view
            #         v.run_command('clone_file')
            #         return

            v = sublime.active_window().open_file('%s:%d:%d' % (def_file, l, c), sublime.ENCODED_POSITION|sublime.TRANSIENT)
            v = sublime.active_window().views_in_group(1)[0]
            v.run_command('append', {'characters': open(cur_file).read(), 'force': True, 'scroll_to_end': False})
            v.set_read_only(True)
            v.show_at_center(v.text_point(l, c))
            sublime.active_window().set_view_index(v, 1, 0)
            
        self.cked = not self.cked
        if self.cked:
            sublime.active_window().run_command("set_layout",
                        {
                            "cols": [0.0, 0.5, 1.0],
                            "rows": [0.0, 1.0],
                            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]
                        })
            # v = sublime.active_window().new_file()
            # sublime.active_window().set_view_index(v, 1, 0)
            on_selection_view_in_right = view_def_in_right
        else:
            sublime.active_window().run_command("set_layout",
                        {
                            "cols": [0.0, 1.0],
                            "rows": [0.0, 1.0],
                            "cells": [[0, 0, 1, 1]]
                        })
            on_selection_view_in_right = None

    def is_enabled(self):
        view = sublime.active_window().active_view()
        cur_file = get_view_file(view)
        line, column = get_view_cur(view)
        if not isinstance(proj, Projector):
            return False
        if len(view.window().views_in_group(1)) > 0:
            return False
        return True

    def is_checked(self):
        return self.cked

class SclangOpen(sublime_plugin.TextCommand):
    def run(self, edit, opener):
        global proj
        cur_win = self.view.window()
        for v in cur_win.views():
            v.close()
        proj = Projector()
        proj.set_work_path(opener['workpath'])
        for inc in opener['sys_inc']:
            proj.add_sys_include_path(inc)
        for inc in opener['usr_inc']:
            proj.add_usr_include_path(inc)
        for f in opener['c_files']:
            proj.add_file(f)
            cur_win.open_file(f)
        proj.set_arguments(opener['args'])
        def show_progess(msg):
            sublime.status_message(msg)
        clangfolder = os.path.join(opener['workpath'], '.clang_data')
        if not os.path.exists(clangfolder):
            os.mkdir(clangfolder)
        proj.compile(progress_callback=show_progess)


class SclangGoto(sublime_plugin.TextCommand):
    def run(self, edit):
        cur_file = get_view_file(self.view)
        line, column = get_view_cur(self.view)
        if not isinstance(proj, Projector):
            return
        cur = proj.get_def_of(cur_file, line, column)
        if cur is None:
            return
        if cur is not None:
            self.view.run_command('push_selection')
            def_file = cur.location.file.name
            l, c = location_to_pos(cur.location)
            self.view.window().open_file('%s:%d:%d' % (def_file, l, c), sublime.ENCODED_POSITION)


    def is_enabled(self):
        view = sublime.active_window().active_view()
        cur_file = get_view_file(view)
        line, column = get_view_cur(view)
        if not isinstance(proj, Projector):
            return False
        cur = proj.get_def_of(cur_file, line, column)
        if cur:
            return True
        else:
            return False


class SclangView(sublime_plugin.TextCommand):
    def run(self, edit):
        global outer
        cur_file = get_view_file(self.view)
        line, column = get_view_cur(self.view)
        if not isinstance(proj, Projector):
            return
        curs = proj.find_cursor(cur_file, line, column)
        cur_dict = dict()
        for cur in curs:
            # print(cur.referenced, cur.location.file.name, cur.location.line)
            if cur.location.file.name not in cur_dict:
                cur_dict[cur.location.file.name] = dict()
            cur_dict[cur.location.file.name][cur.location.line] = (
                        proj.get_line(cur.location.file.name, cur.location.line))
        outer = find_sym_panel(self.view.window())
        for (f, cs) in cur_dict.items():
            # outer.add_file(f)
            new_list = [c for c in cs.items()]
            # print(new_list)
            new_list.sort(key=lambda m:m[0])
            for c in new_list: #cs.items():
                outer.add_line('%s:%d' % (os.path.normpath(f), c[0]), c[1])

    def is_enabled(self):
        view = sublime.active_window().active_view()
        cur_file = get_view_file(view)
        line, column = get_view_cur(view)
        if not isinstance(proj, Projector):
            return False
        cur = proj.get_cursor_at(cur_file, line, column);
        if cur is None:
            return False
        cur = cur.get_definition() or cur.referenced
        if cur:
            return True
        else:
            return False


class SclangSwitchfile(sublime_plugin.TextCommand):
    def run(self, edit):
        cur_file = get_view_file(self.view)
        line, column = get_view_cur(self.view)
        if not isinstance(proj, Projector):
            return
        filename = proj.get_include(cur_file, line)
        self.view.window().open_file(filename)

    def is_enabled(self):
        cur_file = get_view_file(self.view)
        line, column = get_view_cur(self.view)
        if not isinstance(proj, Projector):
            return False
        if proj.get_include(cur_file, line):
            return True
        else:
            return False

def GetAutoCompletion(prefix, results):
    comp = list()
    for item in results:
        if True: #item.string.availability != 3:
            place_holder_index = 1
            display_string = []
            insert_string = []
            for field in item.string:
                if field.isKindTypedText():
                    typed = field.spelling
                    # if typed.startswith(prefix):
                    insert_string.append(field.spelling)
                    # else:
                        # break
                elif field.isKindPlaceHolder():
                    insert_string.append( "${%d:%s}" % (place_holder_index, field.spelling) )
                    place_holder_index += 1
                elif field.isKindResultType():
                    pass
                elif str(field.kind) == "LeftBrace":
                    insert_string.append(field.spelling)
                    insert_string.append("\n\t")
                else:
                    insert_string.append(field.spelling)
                display_string.append(field.spelling)
                if field.isKindResultType():
                    display_string.append(" ")
            if len(insert_string) == 0:
                continue
            if item.string.briefComment is not None:
                display_string.append(str(item.string.briefComment))
            disstr = "".join(display_string)
            insstr = "".join(insert_string)
            priority = item.string.priority
            comp.append((priority, ("%s   \t%s" %
                            (typed, disstr),
                            insstr)))
    comp.sort(key=lambda m:m[0])
    comp = [m[1] for m in comp]
    return comp

class ClangComplete(sublime_plugin.TextCommand):
    def run(self, edit, characters):
        file_base = get_view_file(self.view)
        for region in self.view.sel():
            self.view.insert(edit, region.end(), characters)
        end = self.view.sel()[0].begin()
        start = self.view.line(self.view.sel()[0]).begin()
        preline = self.view.substr(sublime.Region(start, end))
        if re.match('\s*#include\s*[\"\<]{1}.*', preline) is not None:
            self.view.run_command("hide_auto_complete")
            sublime.set_timeout(self.delayed_complete, 1)
        if  re.match(".*[a-z]{1}[a-z0-9]*(\.|-\>)$", preline) is not None:
            self.view.run_command("hide_auto_complete")
            sublime.set_timeout(self.delayed_complete, 1)

    def delayed_complete(self):
        self.view.run_command("auto_complete")

class STClangListener(sublime_plugin.EventListener):
    def on_load(self, view):
        global func_on_load
        if func_on_load:
            print(func_on_load)
            func_on_load(self, view)
        func_on_load = None

    def on_post_save(self, view):
        import time
        t = time.time()
        cur_file = get_view_file(view)
        proj.re_compile(cur_file)
        print(time.time()-t)

    def on_selection_modified_async(self, view):
        import re
        if not view.is_in_edit():
            return
        if proj is None:
            return

        if view.name() == 'find_sym_panel':
            try:
                cont = view.substr(view.full_line(view.sel()[0].begin()))
            except Exception as e:
                return
            view.window().run_command("pop_selection")
            filename = re.match('^(?P<filename>.*:\d+)', cont).group('filename')
            view.window().open_file(filename, sublime.ENCODED_POSITION)
            return

        if view.name() == 'error_panel':
            try:
                cont = view.substr(view.full_line(view.sel()[0].begin()))
                if not cont.startswith('line: '):
                    return
                filename = view.substr(view.full_line(view.text_point(0, 0))).strip()
            except Exception as e:
                return
            view.window().run_command("pop_selection")
            line = re.match('^line:\s+(?P<line>\d+).*', cont).group('line')
            print('%s:%s' % (filename, line))
            view.window().open_file('%s:%s' % (filename, line), sublime.ENCODED_POSITION)
            return

        if view.file_name() is not None and len(view.file_name()) > 0:
            if on_selection_view_in_right is not None:
                cur_file = get_view_file(view)
                line, column = get_view_cur(view)
                on_selection_view_in_right(cur_file, line, column)

    def on_query_completions(self, view, prefix, locations):
        cur_file = get_view_file(view)
        # line, column = get_view_cur(view)
        line, column = view.rowcol(locations[0])
        fileCont = view.substr(sublime.Region(0, view.size()))
        if not isinstance(proj, Projector):
            return []
        ret = proj.code_complete(cur_file, line, column, fileCont)
        if ret is None:
            return []
        comp = GetAutoCompletion(prefix, ret.results)
        return (comp, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def on_activated(self, view):
        cur_file = get_view_file(view)
        if not isinstance(proj, Projector):
            return
        errors = proj.get_errors(cur_file)
        if errors and len(errors)>0:
            ep = error_panel(view.window())
            ep.add_line(errors[0]['file'])
            for e in errors:
                if e['line'] > 99999:
                    sublime.message_dialog('file toooooo long')
                    return
                ep.add_line('line: %5d [%s] %s' % (e['line'], e['severity'], e['string']))
            ep.show()
        # else:
        #     ep = error_panel(view.window())
        #     ep.hide()
    def on_clone(self, view):
        global on_clone_callback
        if on_clone_callback is not None:
            on_clone_callback(view)
            on_clone_callback = None
