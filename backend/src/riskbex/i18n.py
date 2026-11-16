"""Local presentation translations. English message IDs are stable source keys.

Only this adapter translates render arguments. Widget values, API payloads, cached
loaders and financial functions retain their original identifiers and numbers.
No monkey-patching of Streamlit, network access or locale-global mutation.
"""
import json
from pathlib import Path
import re

import streamlit as streamlit
from streamlit.runtime.scriptrunner import get_script_run_ctx

LANGUAGES = {'en': '🇬🇧 English', 'es': '🇪🇸 Español'}
ES = json.loads(Path(__file__).with_name('translations_es.json').read_text(encoding='utf-8'))
EN = {key: key for key in ES}
CATALOGS = {'en': EN, 'es': ES}
CASEFOLD_ES = {key.casefold(): value for key, value in ES.items()}


def language():
    if get_script_run_ctx(suppress_warning=True) is None:
        return 'en'
    return streamlit.session_state.get('ui_language', 'en')


def normalize(text):
    return ' '.join(text.split())


# Templates match already formatted values; their captured numbers are never
# parsed, rounded, recalculated or sent back to the API.
def template_pattern(key):
    parts = re.split(r'(\{\d+\})', key)
    names = []
    pattern = ''
    for part in parts:
        if re.fullmatch(r'\{\d+\}', part):
            name = part[1:-1]
            capture = r'[\d,]+' if name == '0' and key.startswith('{0} {1} sessions:') else '.+?'
            pattern += '(?P<p' + name + '>' + capture + ')' if name not in names else '(?P=p' + name + ')'
            names.append(name)
        else:
            pattern += re.escape(part)
    return re.compile(pattern, re.IGNORECASE)


TEMPLATES = sorted([(template_pattern(k), v) for k, v in ES.items() if re.search(r'\{\d+\}', k)],
                   key=lambda item: len(item[0].pattern), reverse=True)


def translate(text, lang=None, _depth=0):
    """Translate a message or formatted template; unknown keys fall back to EN."""
    lang = lang or language()
    if not isinstance(text, str) or lang not in CATALOGS or lang == 'en' or _depth > 8:
        return text
    if '<style>' in text:
        return text
    # Preserve markup/attributes verbatim. Translate text nodes, not CSS, URLs or
    # HTML identifiers. aria-label is the sole translatable attribute in our HTML.
    if re.search(r'<[a-zA-Z/][^>]*>', text):
        parts = re.split(r'(<[^>]+>)', text)
        return ''.join(re.sub(r'aria-label="([^"]+)"',
                             lambda m: 'aria-label="' + translate(m[1], lang, _depth + 1) + '"', part)
                       if part.startswith('<') else translate(part, lang, _depth + 1) for part in parts)
    key = normalize(text)
    if not key:
        return text
    if key.startswith("**") and key.endswith("**") and key.count("**") == 2:
        return "**" + translate(key[2:-2], lang, _depth + 1) + "**"
    if key.startswith("### "):
        return "### " + translate(key[4:], lang, _depth + 1)
    translated = CATALOGS[lang].get(key, CASEFOLD_ES.get(key.casefold()))
    if translated is None:
        for pattern, replacement in TEMPLATES:
            match = pattern.fullmatch(key)
            if match:
                translated = re.sub(r'\{(\d+)\}',
                                    lambda m: translate(match['p' + m[1]], lang, _depth + 1), replacement)
                break
    if translated is None:
        # Markdown and composed stories have structural separators, not arbitrary
        # substring replacement. This also localizes labels inside comparisons.
        for separator in ('; ', ' — ', ' · ', '\n'):
            if separator in text:
                return separator.join(translate(p, lang, _depth + 1) for p in text.split(separator))
        if key.startswith('**') and key.endswith('**'):
            translated = '**' + translate(key[2:-2], lang, _depth + 1) + '**'
        elif key.startswith('### '):
            translated = '### ' + translate(key[4:], lang, _depth + 1)
        elif key.endswith('.') and key[:-1] in ES:
            translated = ES[key[:-1]] + '.'
        elif key.endswith("."):
            bare = translate(key[:-1], lang, _depth + 1)
            translated = bare + "." if bare != key[:-1] else text
        else:
            return text
    # Keep boundary whitespace for adjacent HTML nodes and string composition.
    return text[:len(text) - len(text.lstrip())] + translated + text[len(text.rstrip()):]


def display_frame(frame):
    """Copy presentation data; never mutate API frames or their numeric values."""
    import pandas as pd
    if language() == 'en' or not isinstance(frame, (pd.DataFrame, pd.Series)):
        return frame
    result = frame.copy(deep=True)
    if isinstance(result, pd.Series):
        result.name = translate(result.name)
    else:
        for column in result.columns:
            if result[column].dtype == object or isinstance(result[column].dtype, pd.StringDtype):
                result[column] = result[column].map(lambda value: translate(value) if isinstance(value, str) else value)
        result = result.rename(columns=lambda c: translate(c))
    result.index.name = translate(result.index.name)
    return result


def chart_spec(chart):
    """Translate Vega display metadata and categorical labels, retaining fields."""
    spec = chart.to_dict()
    if language() == 'en':
        return spec

    def visit(value):
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: visit(item) for key, item in value.items()}
        for key in ('title', 'text'):
            if isinstance(result.get(key), str):
                result[key] = translate(result[key])
        if 'field' in result and 'title' not in result:
            result['title'] = translate(result['field'])
        if isinstance(result.get('domain'), list):
            result['domain'] = [translate(item) for item in result['domain']]
        return result

    spec = visit(spec)
    # Dataset column names remain internal; only categorical cell labels change.
    for rows in spec.get('datasets', {}).values():
        for row in rows:
            for key, value in row.items():
                if isinstance(value, str):
                    row[key] = translate(value)
    return spec


class Presentation:
    """Small explicit adapter around native Streamlit rendering boundaries."""
    TEXT = {'title', 'header', 'subheader', 'markdown', 'caption', 'text', 'info',
            'warning', 'error', 'success', 'spinner', 'expander', 'popover',
            'button', 'form_submit_button', 'number_input', 'metric'}
    CHOICES = {'radio', 'selectbox', 'multiselect', 'segmented_control'}
    FRAMES = {'dataframe', 'table', 'line_chart', 'area_chart', 'bar_chart'}

    def __init__(self, target):
        self.target = target

    def __enter__(self):
        self.target.__enter__()
        return self

    def __exit__(self, *args):
        return self.target.__exit__(*args)

    def __getattr__(self, name):
        method = getattr(self.target, name)
        if name in self.CHOICES:
            def choice(label, options, *args, **kwargs):
                original = kwargs.pop('format_func', str)
                selected_language = language()
                kwargs['format_func'] = lambda value: translate(original(value), selected_language)
                return method(translate(label), options, *args, **kwargs)
            return choice
        if name in self.TEXT or name == 'write':
            def text(*args, **kwargs):
                for key in ('help', 'placeholder'):
                    if key in kwargs:
                        kwargs[key] = translate(kwargs[key])
                return method(*(translate(arg) for arg in args), **kwargs)
            return text
        if name == 'tabs':
            return lambda labels, **kwargs: [Presentation(item) for item in method([translate(s) for s in labels], **kwargs)]
        if name == 'columns':
            return lambda *args, **kwargs: [Presentation(item) for item in method(*args, **kwargs)]
        if name in {'container', 'form', 'empty'}:
            return lambda *args, **kwargs: Presentation(method(*args, **kwargs))
        if name in self.FRAMES:
            def frame(data, *args, **kwargs):
                if language() == 'es' and name in {'line_chart', 'area_chart', 'bar_chart'}:
                    kwargs.setdefault('x_label', translate('Session'))
                    kwargs.setdefault('y_label', translate('Value'))
                return method(display_frame(data), *args, **kwargs)
            return frame
        if name == 'altair_chart':
            return lambda chart, **kwargs: self.target.vega_lite_chart(chart_spec(chart), **kwargs)
        if name == 'pyplot':
            def pyplot(fig, **kwargs):
                from matplotlib.text import Text
                for artist in fig.findobj(Text):
                    artist.set_text(translate(artist.get_text()))
                return method(fig, **kwargs)
            return pyplot
        if name == 'image':
            def image(*args, **kwargs):
                if 'caption' in kwargs:
                    kwargs['caption'] = translate(kwargs['caption'])
                return method(*args, **kwargs)
            return image
        return method


ui = Presentation(streamlit)


def _select_language():
    # A selected segment can be clicked again to clear it. Keep a valid language.
    selected = streamlit.session_state.ui_language or streamlit.session_state._last_ui_language
    streamlit.session_state.ui_language = selected
    streamlit.session_state._last_ui_language = selected
    streamlit.query_params["lang"] = selected


def render_language_selector():
    """Native segments; language names remain usable without flag rendering."""
    if 'ui_language' not in streamlit.session_state:
        requested = streamlit.query_params.get('lang', 'en')
        streamlit.session_state.ui_language = requested if requested in LANGUAGES else 'en'
    streamlit.session_state._last_ui_language = streamlit.session_state.ui_language
    # The URL initializes a new session; thereafter session state is authoritative.
    # Also normalize missing/invalid URL values without touching the current view.
    if streamlit.query_params.get('lang') != streamlit.session_state.ui_language:
        streamlit.query_params['lang'] = streamlit.session_state.ui_language
    with streamlit.container(horizontal=True, horizontal_alignment='right'):
        streamlit.segmented_control('Language / Idioma', list(LANGUAGES), key='ui_language',
                        format_func=LANGUAGES.get, on_change=_select_language,
                        selection_mode='single', label_visibility='collapsed', width='content')
