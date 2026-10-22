#!/usr/bin/env python3
"""Syntax-highlighted, escaped unified excerpt diffs. Requires Pygments."""
import argparse
import difflib
import html
import json
import re
from pathlib import Path
from pygments.lexers import get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

EXTENSIONS = {'.swift':'swift','.m':'objective-c','.mm':'objective-c++','.h':'objective-c',
    '.c':'c','.cc':'cpp','.cpp':'cpp','.hpp':'cpp','.py':'python','.sh':'bash','.zsh':'bash',
    '.bash':'bash','.json':'json','.yml':'yaml','.yaml':'yaml','.xml':'xml','.plist':'xml',
    '.storyboard':'xml','.xib':'xml','.rb':'ruby','.js':'javascript','.ts':'typescript',
    '.sql':'sql','.md':'markdown','.proto':'protobuf','.metal':'metal','.glsl':'glsl',
    '.toml':'toml','.xcconfig':'ini'}
ALIASES = {'sh':'bash','shell':'bash','zsh':'bash','objc':'objective-c','obj-c':'objective-c',
    'objc++':'objective-c++','objectivec':'objective-c','c++':'cpp','yml':'yaml','js':'javascript',
    'ts':'typescript','md':'markdown','text':'text','plaintext':'text'}
RUBY_FILES = {'Podfile','Gemfile','Fastfile','Appfile','Matchfile','Snapfile','Scanfile','Brewfile','Rakefile'}


def language_for(file):
    name = file['path'].split(' → ')[0].split(' · ')[0]
    basename = Path(name).name
    language = file.get('language') or ('ruby' if basename in RUBY_FILES else
        'make' if basename in {'Makefile','GNUmakefile'} else EXTENSIONS.get(Path(name).suffix.lower(),'text'))
    language = ALIASES.get(language.lower(),language.lower())
    grammar = 'cpp' if language == 'metal' else language
    try:
        lexer = get_lexer_by_name(grammar, stripnl=False, ensurenl=False, tabsize=0)
    except ClassNotFound:
        return get_lexer_by_name('text'), 'text', 'Text'
    return lexer, language, 'Metal · C++ grammar' if language == 'metal' else lexer.name


def token_class(token):
    if token in Token.Comment.Preproc: return 'preprocessor'
    if token in Token.Comment: return 'comment'
    if token in Token.Literal.String: return 'string'
    if token in Token.Literal.Number: return 'number'
    if token in Token.Keyword.Type or token in Token.Name.Class: return 'type'
    if token in Token.Keyword: return 'keyword'
    if token in Token.Name.Function: return 'function'
    if token in Token.Name.Decorator or token in Token.Name.Attribute: return 'attribute'
    if token in Token.Name.Builtin: return 'builtin'
    if token in Token.Name.Tag: return 'tag'
    if token in Token.Operator: return 'operator'
    if token in Token.Punctuation: return 'punctuation'
    return ''


def syntax_lines(source, lexer):
    # Lex entire snippets; splitting first would break multiline string/comment state.
    runs = [(offset,offset+len(value),token_class(token))
            for offset,token,value in lexer.get_tokens_unprocessed(source)]
    result, start, cursor = [], 0, 0
    for full in source.splitlines(keepends=True):
        line = full.rstrip('\r\n')
        classes = [''] * len(line)
        while cursor < len(runs) and runs[cursor][1] <= start: cursor += 1
        i = cursor
        while i < len(runs) and runs[i][0] < start + len(line):
            a,b,kind = runs[i]
            classes[max(0,a-start):min(len(line),b-start)] = [kind] * max(0,min(len(line),b-start)-max(0,a-start))
            i += 1
        result.append(classes)
        start += len(full)
    return result


def replacement_masks(old, new):
    a,b = re.findall(r'\w+|[^\w]+',old),re.findall(r'\w+|[^\w]+',new)
    left,right = [False]*len(old),[False]*len(new)
    ao,bo = [0],[0]
    for token in a: ao.append(ao[-1]+len(token))
    for token in b: bo.append(bo[-1]+len(token))
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if tag != 'equal':
            left[ao[i]:ao[j]] = [True]*(ao[j]-ao[i])
            right[bo[k]:bo[l]] = [True]*(bo[l]-bo[k])
    return left,right


def format_line(value, classes=None, mask=None):
    classes = classes if classes is not None else ['']*len(value)
    mask = mask if mask is not None else [False]*len(value)
    output, i = [], 0
    while i < len(value):
        j = i+1
        while j < len(value) and (classes[j],mask[j]) == (classes[i],mask[i]): j += 1
        text = html.escape(value[i:j])
        if classes[i]: text = f'<span class="tok-{classes[i]}">{text}</span>'
        if mask[i]: text = f'<mark>{text}</mark>'
        output.append(text)
        i = j
    return ''.join(output)


def emphasized_pair(old,new):
    a,b = replacement_masks(old,new)
    return format_line(old,mask=a),format_line(new,mask=b)


def render_file(file):
    before,after = file.get('before',''),file.get('after','')
    old,new = before.splitlines(),after.splitlines()
    if not old and not new: return ''
    lexer,language,label = language_for(file)
    old_syntax,new_syntax = syntax_lines(before,lexer),syntax_lines(after,lexer)
    rows = []
    def line(kind,value,old_number='',new_number='',mask=None):
        styles = None if kind in ('hunk','meta') else new_syntax[new_number-1] if kind == 'add' else old_syntax[old_number-1]
        marker = {'del':'-','add':'+','context':' ','hunk':'','meta':''}[kind]
        rows.append(f'<div class="diff-line {kind}" data-old="{old_number}" data-new="{new_number}">'
            f'<span class="diff-no" aria-hidden="true">{old_number}</span><span class="diff-no" aria-hidden="true">{new_number}</span>'
            f'<span class="diff-prefix">{marker}</span><code>{format_line(value,styles,mask)}</code></div>')
    for group in difflib.SequenceMatcher(None,old,new,autojunk=False).get_grouped_opcodes(3):
        first,last = group[0],group[-1]
        a,c = first[1],first[3]
        line('hunk',f'@@ -{a+1 if last[2]>a else a},{last[2]-a} +{c+1 if last[4]>c else c},{last[4]-c} @@')
        for tag,a,b,c,d in group:
            if tag == 'equal':
                for i in range(b-a): line('context',old[a+i],a+i+1,c+i+1)
            else:
                left,right = {},{}
                if tag == 'replace':
                    candidates = sorted(((difflib.SequenceMatcher(None,old[i],new[j],autojunk=False).ratio(),i,j)
                        for i in range(a,b) for j in range(c,d)),reverse=True)
                    for ratio,i,j in candidates:
                        if ratio >= .45 and i not in left and j not in right: left[i],right[j] = replacement_masks(old[i],new[j])
                for i in range(a,b): line('del',old[i],i+1,mask=left.get(i))
                for i in range(c,d): line('add',new[i],new_number=i+1,mask=right.get(i))
    if not rows and old and old == new and before.endswith(('\n','\r')) != after.endswith(('\n','\r')):
        start = max(0,len(old)-3)
        line('hunk',f'@@ -{start+1},{len(old)-start} +{start+1},{len(new)-start} @@')
        for i in range(start,len(old)-1): line('context',old[i],i+1,i+1)
        line('del',old[-1],len(old))
        if not before.endswith(('\n','\r')): line('meta','\\ No newline at end of excerpt')
        line('add',new[-1],new_number=len(new))
        if not after.endswith(('\n','\r')): line('meta','\\ No newline at end of excerpt')
    if not rows:
        for i,value in enumerate(old): line('context',value,i+1,i+1)
    path = file['path']
    old_path,new_path = file.get('before_path',path.split(' → ')[0]),file.get('after_path',path.split(' → ')[0])
    note = file.get('note','Excerpt diff; uncompiled')
    return (f'<section class="module diff-file" data-language="{html.escape(language,quote=True)}" '
        f'data-before="{html.escape(json.dumps(before),quote=True)}" data-after="{html.escape(json.dumps(after),quote=True)}">'
        f'<h5>{html.escape(file["owner"])}<span class="code-language">{html.escape(label)}</span></h5>'
        f'<div class="file"><h6>{html.escape(path)}</h6><div class="diff-paths"><div>--- a/{html.escape(old_path)}</div>'
        f'<div>+++ b/{html.escape(new_path)}</div></div><div class="diff-code" role="group" aria-label="Proposed code diff">'
        + ''.join(rows) + '</div>' + (f'<span class="diff-context" title="{html.escape(note,quote=True)}">excerpt</span>' if note else '')
        + '</div></section>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = '\n'.join(render_file(file) for file in json.loads(args.input.read_text(encoding='utf-8'))['files'])
    if args.output: args.output.write_text(result, encoding='utf-8')
    else: print(result)
