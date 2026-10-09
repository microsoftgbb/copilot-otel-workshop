"""Every relative Markdown link in the repository must resolve."""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)#\s]+)")


class LinkTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        broken = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
            for name in files:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(base, name)
                with open(path) as fh:
                    text = fh.read()
                for m in LINK.finditer(text):
                    target = os.path.normpath(os.path.join(base, m.group(1)))
                    if not os.path.exists(target):
                        broken.append(f"{os.path.relpath(path, ROOT)} -> {m.group(1)}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
