# This file is the actual code for the custom Python FS provider smb_fs-provider

from dataiku.fsprovider import FSProvider
import os
import smbclient
from smbclient import listdir, mkdir, register_session, rmdir, scandir, open_file, shutil, remove, utime
from smbclient.path import isdir, isfile, exists, getsize, getatime, getmtime

"""
This sample provides files from inside the providerRoot passed in the config
"""
class CustomFSProvider(FSProvider):
    def __init__(self, root, config, plugin_config):
        """
        :param root: the root path for this provider
        :param config: the dict of the configuration of the object
        :param plugin_config: contains the plugin settings
        """
        if len(root) > 0 and root[0] == '/':
            root = root[1:]
        self.root = root  
        self.provider_root = '/'

        # get plugin config values
        self.preset = config['presets']
        self.smb_username = self.preset['smb_username']
        self.smb_password = self.preset['smb_password']
        self.smb_host = self.preset['smb_host']
        self.smb_client_name = self.preset['smb_client_name']
        self.smb_server_name = self.preset['smb_server_name']
        self.smb_port = self.preset['smb_port']
        self.smb_share = self.preset['smb_share']
        self.smb_domain_controller = self.preset['smb_domain_controller']

        
        # save server_uri 
        self.server_uri = '\\\\' + self.smb_host + '\\' + self.smb_share 
           
        # Connect to SMB share
        smbclient.register_session(
            server=self.smb_host, 
            username=self.smb_username, 
            password=self.smb_password,
            port=self.smb_port
        )


    # util methods
    def get_rel_path(self, path):
        if len(path) > 0 and path[0] == '/':
            path = path[1:]
        return path
    
    def get_lnt_path(self, path):
        if len(path) == 0 or path == '/':
            return '/'
        elts = path.split('/')
        elts = [e for e in elts if len(e) > 0]
        return '/' + '/'.join(elts)
    
    def get_full_path(self, path):
        path_elts = [self.provider_root, self.get_rel_path(self.root), self.get_rel_path(path)]
        path_elts = [e for e in path_elts if len(e) > 0]
        return os.path.join(*path_elts)
    
    def get_smb_path(self, path):
        return self.server_uri + self.samba_style(path)
    
    def samba_style(self, path):
        return path.replace("/", "\\")     
    
    # callbacks
    def close(self):
        """
        Perform any necessary cleanup
        """
        print ('close')

    def stat(self, path):
        """
        Get the info about the object at the given path inside the provider's root, or None 
        if the object doesn't exist
        """
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)
        print("path: " + path )
        print("full_path: " + full_path )
        print("smb_path: " + smb_path )
        if isfile(smb_path):
            stats = smbclient.stat(smb_path)
            return {'path': self.get_lnt_path(full_path), 'size': stats.st_size, 'lastModified': int(stats.st_mtime) * 1000, 'isDirectory':False}            
        elif isdir(smb_path):
            stats = smbclient.stat(smb_path)
            return {'path': self.get_lnt_path(full_path), 'size': 0, 'lastModified':int(stats.st_mtime) * 1000, 'isDirectory':True}
        else:
            return None
    
    def set_last_modified(self, path, last_modified):
        """
        Set the modification time on the object denoted by path. Return False if not possible
        """
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)
        utime(smb_path, (getatime(smb_path), last_modified / 1000))
        return True
 
        
    def browse(self, path):
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)
        
        if not exists(smb_path):
            return {'fullPath' : None, 'exists' : False}
        elif isfile(smb_path):
            return {'fullPath' : self.get_lnt_path(path), 'exists' : True, 'directory' : False, 'size' : getsize(smb_path)}
        else:
            children = []
            for sub in listdir(smb_path):
                sub_full_path = os.path.join(full_path, sub)
                smb_sub_full_path = self.get_smb_path(sub_full_path)
                sub_path = self.get_lnt_path(os.path.join(path, sub))
                #smb_sub_path = samba_style(sub_full_path)
                
                if isdir(smb_sub_full_path):
                    children.append({'fullPath' : sub_path, 'exists' : True, 'directory' : True, 'size' : 0})
                else:
                    children.append({'fullPath' : sub_path, 'exists' : True, 'directory' : False, 'size' : getsize(smb_sub_full_path)})
            return {'fullPath' : self.get_lnt_path(path), 'exists' : True, 'directory' : True, 'children' : children}    
        
    def enumerate(self, path, first_non_empty):
        """
        Enumerate files recursively from prefix. If first_non_empty, stop at the first non-empty file.
        
        If the prefix doesn't denote a file or folder, return None
        """
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)
        
        if not exists(smb_path):
            return None
        if isfile(smb_path):
            return [{'path':self.get_lnt_path(path), 'size': getsize(smb_path), 'lastModified': int(getmtime(smb_path)) * 1000}]
        paths = []
        for root, dirs, files in os.walk(full_path):
            for file in files:
                full_sub_path = os.path.join(root, file)
                smb_full_sub_path = get_smb_path(full_sub_path)
                sub_path = full_sub_path[len(os.path.join(self.provider_root, self.root)):]
                paths.append({'path':self.get_lnt_path(sub_path), 'size': getsize(smb_full_sub_path), 'lastModified':int(getmtime(smb_full_sub_path)) * 1000})
        return paths
        
    def delete_recursive(self, path):
        """
        Delete recursively from path. Return the number of deleted files (optional)
        """
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)
        
        if not exists(smb_path):
            return 0
        elif isfile(smb_path):
            remove(smb_path)
            return 1
        else:
            shutil.rmtree(smb_path)
            return 0
            
    def move(self, from_path, to_path):
        """
        Move a file or folder to a new path inside the provider's root. Return false if the moved file didn't exist
        """

        full_from_path = self.get_full_path(from_path)
        smb_from_path = self.get_smb_path(full_from_path)
        full_to_path = self.get_full_path(to_path)
        smb_to_path = self.get_smb_path(full_to_path)
        if exists(smb_from_path):
            if from_path != to_path:
                shutil.move(smb_from_path, smb_to_path)
            return True
        else:
            return False
            
    def read(self, path, stream, limit):
        """
        Read the object denoted by path into the stream. Limit is an optional bound on the number of bytes to send
        """
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)

        if not isfile(smb_path):
            raise Exception('Path doesn''t exist')
        
        with open_file(smb_path, mode="rb") as fd:
            stream.write(fd.read())
            
    def write(self, path, stream):
        """
        Write the stream to the object denoted by path into the stream
        """
        full_path = self.get_full_path(path)
        smb_path = self.get_smb_path(full_path)
        full_path_parent = self.samba_style(os.path.dirname(full_path))
        smb_path_parent = self.server_uri + full_path_parent
        
        print('FULL: ' + full_path_parent)
        
        if not exists(smb_path_parent):
            mkdir(smb_path_parent)
        with open_file(smb_path, 'wb') as f:
            shutil.copyfileobj(stream, f)
