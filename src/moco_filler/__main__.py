"""``python -m moco_filler`` entry point.

Delegates to ``cli.main()`` so the module-form invocation and the
``moco-filler`` console script registered in ``pyproject.toml`` share
exactly one entrypoint per Constitution §V (single responsibility).
"""

import sys

from moco_filler.cli import main


if __name__ == "__main__":
    sys.exit(main())
