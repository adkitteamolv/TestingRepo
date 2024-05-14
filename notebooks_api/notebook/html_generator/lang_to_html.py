"""language script to html converter module"""
from pygments import highlight
from pygments.lexers import get_lexer_for_filename
from pygments.formatters.html import HtmlFormatter

# pylint: disable=invalid-name, redefined-builtin

def hilite_me(code, ext):
    """
    Formats the code to HTML by the using lexer
    as per the file extension(ext)
    :param code:
    :param ext:
    :return:
    """
    style = 'colorful'
    defstyles = 'overflow:auto;width:auto;'

    formatter = HtmlFormatter(style=style,
                              linenos=False,
                              noclasses=True,
                              cssstyles=defstyles)

    # Replacing .r with .R as .r takes REBOL lexer
    if ext == '.r':
        ext = '.R'

    html = highlight(code, get_lexer_for_filename(ext), formatter)
    return html
