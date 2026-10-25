"""Exercise exact Git index reads with synthetic, non-secret negative data."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PublicationPolicy(unittest.TestCase):
    def test_staged_blob_is_reviewed_even_when_worktree_is_clean(self):
        base=ROOT/'out/tests';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='policy-',dir=base) as directory:
            root=Path(directory);(root/'tools').mkdir()
            shutil.copy2(ROOT/'tools/check_publication.py',root/'tools/check_publication.py')
            subprocess.run(['git','init','--initial-branch=codex/policy-test'],cwd=root,check=True,capture_output=True)
            subprocess.run(['git','config','core.autocrlf','false'],cwd=root,check=True)
            # Deliberately assembled so the test source itself does not carry
            # a token, private directory, network endpoint or email literal.
            synthetic=['ghp_'+'A'*40,'C:'+ '/Users/'+'PrivateTest/Documents/example','10.'+'23.45.67','private'+'@example.invalid']
            (root/'sample.txt').write_text('\n'.join(synthetic)+'\n')
            (root/'game.bin').write_bytes(b'\0synthetic only\0')
            subprocess.run(['git','add','--all'],cwd=root,check=True)
            (root/'sample.txt').write_text('Clean worktree; the index still requires rejection.\n')
            def check(staged):
                command=[sys.executable,str(root/'tools/check_publication.py')]+(['--staged'] if staged else [])
                result=subprocess.run(command,cwd=root,capture_output=True,text=True)
                return result.returncode,json.loads(result.stdout)
            status,staged=check(True);_,worktree=check(False)
            self.assertEqual(status,1)
            rules={finding['rule'] for finding in staged['findings']}
            self.assertTrue({'github-token','personal-home-directory','private-network-address','unreviewed-email','excluded-file','binary-content'}<=rules)
            self.assertFalse(any(finding['rule']=='github-token' for finding in worktree['findings']))

if __name__=='__main__':unittest.main()
