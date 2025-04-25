import sys
import traceback

try:
    import moviepy.editor
    import openai
    print('Both packages imported successfully!')
except Exception as e:
    traceback.print_exc()
    print('\nPython path:', sys.path) 