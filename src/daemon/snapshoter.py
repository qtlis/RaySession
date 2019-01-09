import locale
import os
import shutil
import subprocess
import sys
import time
from PyQt5.QtCore import QProcess, QProcessEnvironment

class Snapshoter:
    def __init__(self, session):
        self.session = session
        self.gitname = '.git'
        #process_env = QProcessEnvironment.systemEnvironment()
        #process_env.insert('NSM_URL', self.getServerUrl())
        
        #self.process = QProcess()
        #self.process.setProcessEnvironment(process_env)
        
    def getGitDir(self):
        if not self.session.path:
            raise NameError("attempting to save with no session path !!!")
        
        return "%s/%s" % (self.session.path, self.gitname)
    
    def runGit(self, *args):
        gitdir = self.getGitDir()
        if not gitdir:
            return 
        
        subprocess.run(self.getGitCommandList(*args))
    
    def getGitCommandList(self, *args):
        gitdir = self.getGitDir()
        if not gitdir:
            return []
        
        return ['git', '-C' , self.session.path] + list(args)
    
    def list(self):
        gitdir = self.getGitDir()
        if not gitdir:
            return []
        
        all_list = subprocess.check_output(self.getGitCommandList('tag'))
        all_list_utf = all_list.decode()
        all_tags = all_list_utf.split('\n')
        
        if len(all_tags) >= 1:
            if not all_tags[-1]:
                all_tags = all_tags[:-1]
        
        if len(all_tags) >= 1:
            if all_tags[-1] == 'list':
                all_tags = all_tags[:-1]
        
        return all_tags.__reversed__()
    
    def initSession(self):
        gitdir = self.getGitDir()
        if not gitdir:
            return
        
        print('gitdir', gitdir)
        
        if os.path.exists(gitdir):
            return
        
        print('gitdir2')
        
        self.runGit('init')
        
    def excludeUndesired(self):
        if not self.session.path:
            return
        
        exclude_path = "%s/.git/info/exclude" % self.session.path
        exclude_file = open(exclude_path, 'w')
        
        contents = ""
        for extension in ('wav', 'peak', 'flac', 'ogg', 'mp3', 'midi', 'mid'
                          'avi', 'mp4'):
            contents += "*.%s\n" % extension
        
        contents += '\n'
        
        big_files_all = subprocess.check_output(['find', self.session.path,
                                                 '-size', '+50M'])
        big_files_utf = big_files_all.decode()
        contents += big_files_utf
        
        exclude_file.write(contents)
        exclude_file.close()
    
    def getTagDate(self):
        date = time.localtime()
        tagdate = "%s_%s_%s_%s_%s_%s" % (
                    date.tm_year, date.tm_mon, date.tm_mday,
                    date.tm_hour, date.tm_min, date.tm_sec)
        
        return tagdate
    
    def save(self):
        subprocess.run(['ray-snapshot', self.session.path, self.getTagDate()])
        
    def load(self, spath, snapshot):
        tag_for_last = "%s_,_%s" % (self.getTagDate(), snapshot)
        subprocess.run(['git', '-C', spath, 'tag', '-a', tag_for_last, '-m' 'ray'])
        
        print('reload snapshot')
        subprocess.run(['git', '-C', spath, 'checkout', snapshot])
        print('snapshot reloadded')