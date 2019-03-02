import io
import json
import os
import requests
import xml.etree.ElementTree
import time
import sys
import zipfile
import shutil
from shutil import copy2
import pprint
import collections
import re
import unicore_client

class Nsg:
    key = 'Application_Fitting-DA5A3D2F8B9B4A5D964D4D2285A49C57'
    url = 'https://nsgr.sdsc.edu:8443/cipresrest/v1'
    headers = {'cipres-appkey' : key}
    tool = 'BLUEPYOPT_TG'

    @classmethod
    def checkNsgLogin(cls, username, password):                                           
        KEY = cls.key
        URL = cls.url + '/job/' + username                

        try:
            r = requests.get(URL, auth=(username, password), headers=cls.headers)               
        except Exception as e:
            return {'response':'KO', 'message':e.message}

        root = xml.etree.ElementTree.fromstring(r.text)                                 
        flag = "OK"

        if root.tag == "error":                                                         
            msg = root.find("displayMessage").text                                      
            flag = "KO"
        else:                                                                           
            msg = "Authenticated successfully"                                          

        return {"response": flag, "message": msg}

    @classmethod
    def runNSG(cls, username_submit, password_submit, core_num, node_num, \
            runtime, zfName):
        """
        Launch process on NSG
        """

        CRA_USER = username_submit
        PASSWORD = password_submit
        KEY = cls.key
        URL = cls.url
        TOOL = cls.tool

        payload = {'tool' : TOOL, 'metadata.statusEmail' : 'false', \
                'vparam.number_cores_' : core_num, 'vparam.number_nodes_' :\
                node_num, 'vparam.runtime_' : runtime, 'vparam.filename_': 'init.py'}

        # set file to be submitted
        files = {'input.infile_' : open(zfName,'rb')}

        # submit job with post
        r = requests.post('{}/job/{}'.format(URL, CRA_USER), auth=(CRA_USER, \
            PASSWORD), data=payload, headers=cls.headers, files=files)

        if r.status_code != 200:
            return {"status_code":r.status_code}
        else:

            # format text in xml
            root = xml.etree.ElementTree.fromstring(r.text)

            # extract job selfuri and resulturi
            outputuri = root.find('resultsUri').find('url').text
            selfuri = root.find('selfUri').find('url').text

            # extract job handle
            r = requests.get(selfuri, auth=(CRA_USER, PASSWORD), headers=cls.headers)
            root = xml.etree.ElementTree.fromstring(r.text)
            if not r.status_code == 200:
                jobname = "No jobname because error in submission"
            else:
                jobname = root.find('jobHandle').text

            response = {"status_code":r.status_code, "outputuri":outputuri, \
                    "selfUri":selfuri, "jobname":jobname, "zfName":zfName}
            return response

    @classmethod
    def fetch_job_list(cls, username_fetch, password_fetch):
        """
        Retrieve job list from NSG servers.
        """

        # read/set NSG connection parameters
        KEY = cls.key
        URL = cls.url
        CRA_USER = username_fetch
        PASSWORD = password_fetch

        # 
        r_all = requests.get(URL + "/job/" + CRA_USER, auth=(CRA_USER, \
            PASSWORD), headers=cls.headers)
        root_all = xml.etree.ElementTree.fromstring(r_all.text)

        # create final dictionary
        job_list_dict = collections.OrderedDict()
        job_list = root_all.find('jobs')
        for job in job_list.findall('jobstatus'):
            job_title = job.find('selfUri').find('title').text
            job_url = job.find('selfUri').find('url').text

            job_list_dict[job_title] = collections.OrderedDict()
            job_list_dict[job_title]['url'] = job_url

        return job_list_dict


    @classmethod
    def fetch_job_details(cls, job_id, username_fetch, password_fetch):
        """
        Retrieve details from individual jobs from the job list given as argument
        Current status, current status timestamp and submission timestamp are fetched for every job
        """

        # read/set NSG connection parameters
        KEY = cls.key
        URL = cls.url
        CRA_USER = username_fetch
        PASSWORD = password_fetch

        r_job = requests.get(URL + "/job/" + CRA_USER + '/' + job_id, \
                auth=(CRA_USER, PASSWORD), headers=cls.headers)
        root_job = xml.etree.ElementTree.fromstring(r_job.text)

        job_date_submitted = root_job.find('dateSubmitted').text
        job_res_url = root_job.find('resultsUri').find('url').text
        job_messages = root_job.find('messages').findall('message')
        job_stage = job_messages[-1].find('stage').text
        job_stage_ts = job_messages[-1].find('timestamp').text

        job_info_dict = collections.OrderedDict()
        job_info_dict["job_id"] = job_id 
        job_info_dict["job_date_submitted"] = job_date_submitted
        job_info_dict["job_res_url"] = job_res_url
        job_info_dict["job_stage"] = job_stage
        job_info_dict["job_stage_ts"] = job_stage_ts

        return job_info_dict 

    @classmethod
    def fetch_job_results(cls, job_res_url, username_fetch, password_fetch, \
            opt_res_dir, wf_id):
        """
        Fetch job output files from NSG 
        """
        # read/set NSG connection parameters
        KEY = cls.key
        URL = cls.url
        CRA_USER = username_fetch
        PASSWORD = password_fetch
        opt_res_dir = opt_res_dir

        # request all output file urls 
        r_all = requests.get(job_res_url, auth=(CRA_USER, PASSWORD), \
                headers=cls.headers)
        root = xml.etree.ElementTree.fromstring(r_all.text)
        all_down_uri = root.find('jobfiles').findall('jobfile')

        # create destination dir if not existing
        if not os.path.exists(opt_res_dir):
            os.mkdir(opt_res_dir)

        # for every file download it to the destination dir
        for i in all_down_uri:
            crr_down_uri = i.find('downloadUri').find('url').text
            r = requests.get(crr_down_uri, auth=(CRA_USER, PASSWORD), \
                    headers=cls.headers) 
            d = r.headers['content-disposition']
            filename_list = re.findall('filename=(.+)', d)
            for filename in filename_list:
                with open(os.path.join(opt_res_dir,filename), 'wb') as fd:
                    for chunk in r.iter_content():
                        fd.write(chunk)

        fname = opt_res_dir + '_' +  wf_id

        if os.path.isfile(fname):
            shutil.remove(fname)

        shutil.make_archive(fname, 'zip', opt_res_dir)

        return ""

    #@classmethod
    #def createzip(cls, fin_opt_folder, source_opt_zip, \
    #        opt_name, source_feat, gennum, offsize, zfName):
    #    """
    #    Create zip file to be submitted to NSG 
    #    """

        # folder named as the optimization
     #   if not os.path.exists(fin_opt_folder):
     #       os.makedirs(fin_opt_folder)
     #   else:
     #       shutil.rmtree(fin_opt_folder)
     #       os.makedirs(fin_opt_folder)

        # unzip source optimization file 
     #   z = zipfile.ZipFile(source_opt_zip, 'r')
     #   z.extractall(path = fin_opt_folder)
     #   z.close()

        # change name to the optimization folder
     #   source_opt_name = os.path.basename(source_opt_zip)[:-4]
     #   crr_dest_dir = os.path.join(fin_opt_folder, source_opt_name)
     #   fin_dest_dir = os.path.join(fin_opt_folder, opt_name)
     #   shutil.move(crr_dest_dir, fin_dest_dir)

        # copy feature files to the optimization folder
     #   features_file = os.path.join(source_feat, 'features.json')
     #   protocols_file = os.path.join(source_feat, 'protocols.json') 
     #   fin_feat_path = os.path.join(fin_dest_dir, 'config', 'features.json')
     #   fin_prot_path = os.path.join(fin_dest_dir, 'config', 'protocols.json')
     #   if os.path.exists(fin_feat_path):
     #       os.remove(fin_feat_path)
     #   if os.path.exists(fin_prot_path):
     #       os.remove(fin_prot_path)
     #   shutil.copyfile(features_file, fin_feat_path)
     #   shutil.copyfile(protocols_file, fin_prot_path)

        # change feature files primary keys
     #   fin_morph_path = os.path.join(fin_dest_dir, 'config', 'morph.json')
     #   with open(fin_morph_path, 'r') as morph_file:
     #       morph_json = json.load(morph_file, \
     #               object_pairs_hook=collections.OrderedDict)
     #       morph_file.close()
     #   with open(fin_feat_path, 'r') as feat_file:
     #       feat_json = json.load(feat_file, \
     #               object_pairs_hook=collections.OrderedDict)
     #       feat_file.close()
     #   with open(fin_prot_path, 'r') as prot_file:
     #       prot_json = json.load(prot_file, \
     #               object_pairs_hook=collections.OrderedDict)
     #       prot_file.close()

     #   os.remove(fin_feat_path)
     #   os.remove(fin_prot_path)

     #   fin_key = morph_json.keys()[0]
     #   feat_key = feat_json.keys()[0]
     #   prot_key = prot_json.keys()[0]

     #   feat_json[fin_key] = feat_json.pop(feat_key)
     #   prot_json[fin_key] = prot_json.pop(prot_key)

        # save feature files with changed keys
     #   with open(fin_feat_path, 'w') as feat_file:
     #       feat_file.write(json.dumps(feat_json, indent=4))
     #       feat_file.close()

        # save protocol files with changed keys
     #   with open(fin_prot_path, 'w') as prot_file:
     #       prot_file.write(json.dumps(prot_json, indent=2))
     #       prot_file.close()


        # remove unwanted files from the folder to be zipped
     #   for item in os.listdir(fin_dest_dir):
     #       if item.startswith('init') or item.endswith('.zip') \
     #               or item.startswith('__MACOSX'):
     #                   os.remove(os.path.join(fin_dest_dir, item))

     #   with open(os.path.join(fin_dest_dir, 'init.py'),'w') as f:
     #       f.write('import os')
     #       f.write('\n')
     #       f.write('os.system(\'python opt_neuron.py --max_ngen=' + str(gennum) + ' --offspring_size=' + str(offsize) + ' --start --checkpoint ./checkpoints/checkpoint.pkl\')')
     #       f.write('\n')
     #   f.close()

        # build optimization folder name
     #   crr_dir_opt = os.path.join(fin_opt_folder, opt_name)

     #   foo = zipfile.ZipFile(zfName, 'w', zipfile.ZIP_DEFLATED)

     #   checkpoints_dir = os.path.join(crr_dir_opt, 'checkpoints')
     #   figures_dir = os.path.join(crr_dir_opt, 'figures')
     #   r_0_dir = os.path.join(crr_dir_opt, 'r_0')

     #   if os.path.exists(checkpoints_dir):
     #       shutil.rmtree(checkpoints_dir)
     #       os.makedirs(checkpoints_dir)
     #   if os.path.exists(figures_dir):
     #       shutil.rmtree(figures_dir)
     #       os.makedirs(figures_dir)
     #   if os.path.exists(r_0_dir):
     #       shutil.rmtree(r_0_dir)

     #   for root, dirs, files in os.walk(fin_opt_folder):
     #       if (root == os.path.join(crr_dir_opt, 'morphology')) or \
     #               (root == os.path.join(crr_dir_opt, 'config')) or \
     #               (root == os.path.join(crr_dir_opt, 'mechanisms')) or \
     #               (root == os.path.join(crr_dir_opt, 'model')):
                #
     #           for f in files:
     #               final_zip_fname = os.path.join(root, f)
     #               foo.write(final_zip_fname, \
     #                       final_zip_fname.replace(fin_opt_folder, '', 1))

     #       if (root == os.path.join(crr_dir_opt, 'checkpoints')) or \
     #               (root == os.path.join(crr_dir_opt, 'figures')):
     #                   final_zip_fold_name = os.path.join(root)
     #                   foo.write(final_zip_fold_name, \
     #                           final_zip_fold_name.replace(fin_opt_folder, '',
     #                               1))

     #       if (root == crr_dir_opt):
     #           for f in files:
     #               if f.endswith('.py'):
     #                   final_zip_fname = os.path.join(root, f)
     #                   foo.write(final_zip_fname, \
     #                       final_zip_fname.replace(fin_opt_folder, '', 1))
     #   foo.close()


class Unicore:
    """
    Class for submitting jobs with Unicore
    """
    @classmethod
    def checkLogin(cls, username="", token="", hpc=""):                                           
        auth = unicore_client.get_oidc_auth(token=token) 
        base_url = unicore_client.get_sites()[sys]['url']
        role = unicore_client.get_properties(base_url, auth)['client']['role']['selected']

        resp = {"response" : "KO", "message" : "This account is not \
                    allowed to submit job on " + sys + " booster partition"}
        #
        if role == "user":
            info = unicore_client.get_properties(base_url, auth)['client']['xlogin']['UID']
            UIDs = unicore_client.get_properties(base_url, auth)['client']['xlogin']['availableUIDs']
            if username in UIDs and username[0:3] == "vsk":
                resp = {"response" : "OK", "message" : "Successful authentication"}
            
        return resp



    @classmethod
    def run_unicore_opt(cls, sys="", filename="", joblaunchname = "", \
             token = None, jobname = "UNICORE_Job", core_num = 4, \
             node_num = 2, runtime = 4, username="", hpc = ""):

        # build folder name
        basename = os.path.basename(filename)
        foldname = os.path.splitext(basename)[0] 

        # read file to be moved to remote
        with open(filename, 'r') as f:
            content = f.read()
        f.close()
        modpy = content
        mod = {'To': basename, 'Data': modpy}

        # create inputs array
        inputs = [mod]
        
        # define exec string depending on hpc system
        if hpc == "cscs-pizdaint":
            exec_str = "; chmod +rx *.sbatch; ./ipyparallel.sbatch"
            hpc_sub = ["DAINT-CSCS"]
        elif hpc == "jureca":
            exec_str = "; chmod +rx *.sh; chmod +rx *.sbatch; sh " + joblaunchname + ";",
            hpc_sub = "jureca"

        # create job to be submitted
        job = {}
        job = {"Executable": "unzip " + basename + "; cd " + foldname + exec_str,
                "Name": jobname,
                "Resources": {
                    "Nodes": str(node_num), \
                    "CPUsPerNode": str(core_num), \
                    "Runtime": str(runtime), \
                    "Queue": "booster",
                    },
                }

        auth = unicore_client.get_oidc_auth(token)
        auth['X-UNICORE-User-Preferences'] = 'uid:'+ username 
        base_url = unicore_client.get_sites()[hpc_sub]['url']
        job_url = unicore_client.submit(base_url + '/jobs', job, auth, inputs)

        return job_url


    @classmethod
    def fetch_job_list(cls, sys, token, username):
        """
        Retrieve job list from Unicore systems
        """

        job_list_dict = collections.OrderedDict()

        auth = unicore_client.get_oidc_auth(token=token)
        auth['X-UNICORE-User-Preferences'] = 'uid:'+ username 
        base_url = unicore_client.get_sites()[sys]['url']
        listofjobs = unicore_client.get_properties(base_url + '/jobs', auth)
        jobs = listofjobs['jobs']
        for i in jobs:
            r = unicore_client.get_properties(i, auth) 
            job_list_dict[i] = collections.OrderedDict()
            job_list_dict[i]['url'] = i
            job_list_dict[i]['name'] = r['name']
        return job_list_dict

    @classmethod
    def fetch_job_details(cls, site="", job_res_url="", token=""):
        """
        """
        job_res_url = job_res_url.replace("https:/", "https://")
        job_info_dict = collections.OrderedDict()
        auth = unicore_client.get_oidc_auth(token=token)
        job_date_submitted = unicore_client.get_properties(job_res_url, \
                auth)['submissionTime']
        job_stage = unicore_client.get_properties(job_res_url, \
                auth)['status']
        job_id = unicore_client.get_properties(job_res_url, \
                auth)['name']

        job_info_dict["job_id"] = job_res_url
        job_info_dict["job_date_submitted"] = job_date_submitted
        job_info_dict["job_res_url"] = job_res_url
        job_info_dict["job_stage"] = job_stage

        return job_info_dict

    @classmethod
    def fetch_job_results(cls, job_url="", token="", dest_dir=""):
        """
        """
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        auth = unicore_client.get_oidc_auth(token=token)
        r = unicore_client.get_properties(job_url, auth)
        if (r['status']=='SUCCESSFUL') or (r['status']=='FAILED'):
            wd = unicore_client.get_working_directory(job_url, auth)
            output_files = unicore_client.list_files(wd, auth)
            for file_path in output_files:
                _, f = os.path.split(file_path)
                if (f=='stderr') or (f=="stdout") or (f=="output.zip"):
                    content = unicore_client.get_file_content(wd + "/files" + file_path, auth)
                    with open(os.path.join(dest_dir, f), "w") as local_file:
                        local_file.write(content)
                    local_file.close()


class OptFolderManager:
    """
    """
    @classmethod
    def createzip(cls, fin_opt_folder, source_opt_zip, \
            opt_name, source_feat, gennum, offsize, zfName, hpc, execname="", \
            joblaunchname=""):
        """
        Create zip file to be submitted to HPC systems
        """

        # folder named as the optimization
        if not os.path.exists(fin_opt_folder):
            os.makedirs(fin_opt_folder)
        else:
            shutil.rmtree(fin_opt_folder)
            os.makedirs(fin_opt_folder)

        # unzip source optimization file 
        z = zipfile.ZipFile(source_opt_zip, 'r')
        z.extractall(path = fin_opt_folder)
        z.close()

        # change name to the optimization folder
        source_opt_name = os.path.basename(source_opt_zip)[:-4]
        crr_dest_dir = os.path.join(fin_opt_folder, source_opt_name)
        fin_dest_dir = os.path.join(fin_opt_folder, opt_name)
        shutil.move(crr_dest_dir, fin_dest_dir)

        # copy feature files to the optimization folder
        features_file = os.path.join(source_feat, 'features.json')
        protocols_file = os.path.join(source_feat, 'protocols.json') 
        fin_feat_path = os.path.join(fin_dest_dir, 'config', 'features.json')
        fin_prot_path = os.path.join(fin_dest_dir, 'config', 'protocols.json')
        if os.path.exists(fin_feat_path):
            os.remove(fin_feat_path)
        if os.path.exists(fin_prot_path):
            os.remove(fin_prot_path)
        shutil.copyfile(features_file, fin_feat_path)
        shutil.copyfile(protocols_file, fin_prot_path)

        # change feature files primary keys
        fin_morph_path = os.path.join(fin_dest_dir, 'config', 'morph.json')
        with open(fin_morph_path, 'r') as morph_file:
            morph_json = json.load(morph_file, \
                    object_pairs_hook=collections.OrderedDict)
            morph_file.close()
        with open(fin_feat_path, 'r') as feat_file:
            feat_json = json.load(feat_file, \
                    object_pairs_hook=collections.OrderedDict)
            feat_file.close()
        with open(fin_prot_path, 'r') as prot_file:
            prot_json = json.load(prot_file, \
                    object_pairs_hook=collections.OrderedDict)
            prot_file.close()

        os.remove(fin_feat_path)
        os.remove(fin_prot_path)

        fin_key = morph_json.keys()[0]
        feat_key = feat_json.keys()[0]
        prot_key = prot_json.keys()[0]

        feat_json[fin_key] = feat_json.pop(feat_key)
        prot_json[fin_key] = prot_json.pop(prot_key)

        # save feature files with changed keys
        with open(fin_feat_path, 'w') as feat_file:
            feat_file.write(json.dumps(feat_json, indent=4))
            feat_file.close()

        # save protocol files with changed keys
        with open(fin_prot_path, 'w') as prot_file:
            prot_file.write(json.dumps(prot_json, indent=2))
            prot_file.close()


        if hpc == "nsg":
            OptFolderManager.remove_files_from_opt_folder(fin_dest_dir=fin_dest_dir, hpc=hpc)
            OptFolderManager.add_exec_file(hpc=hpc, fin_dest_dir=fin_dest_dir, execname=execname,\
                    gennum=gennum, offsize=offsize, mod_path="")
        elif hpc == "jureca":
            OptFolderManager.add_exec_file(hpc, fin_dest_dir=fin_dest_dir, execname=execname, \
                    gennum=gennum, offsize=offsize, mod_path="", joblaunchname=joblaunchname)
        elif hpc == "cscs-pizdaint":
            OptFolderManager.add_exec_file(hpc, fin_dest_dir=fin_dest_dir, execname=execname, \
                    gennum=gennum, offsize=offsize, mod_path="", joblaunchname=joblaunchname)

        # build optimization folder name
        crr_dir_opt = os.path.join(fin_opt_folder, opt_name)

        foo = zipfile.ZipFile(zfName, 'w', zipfile.ZIP_DEFLATED)

        checkpoints_dir = os.path.join(crr_dir_opt, 'checkpoints')
        figures_dir = os.path.join(crr_dir_opt, 'figures')
        r_0_dir = os.path.join(crr_dir_opt, 'r_0')

        if os.path.exists(checkpoints_dir):
            shutil.rmtree(checkpoints_dir)
            os.makedirs(checkpoints_dir)
        if os.path.exists(figures_dir):
            shutil.rmtree(figures_dir)
            os.makedirs(figures_dir)
        if os.path.exists(r_0_dir):
            shutil.rmtree(r_0_dir)
        
        full_execname = os.path.join(fin_dest_dir, execname)
        full_joblaunchname = os.path.join(fin_dest_dir, joblaunchname)

        if os.path.exists(full_execname):
            foo.write(full_execname, full_execname.replace(fin_opt_folder, '', 1))
        if os.path.exists(full_joblaunchname):
            foo.write(full_joblaunchname, full_joblaunchname.replace(fin_opt_folder, '', 1))

        for root, dirs, files in os.walk(fin_opt_folder):
            if (root == os.path.join(crr_dir_opt, 'morphology')) or \
                    (root == os.path.join(crr_dir_opt, 'config')) or \
                    (root == os.path.join(crr_dir_opt, 'mechanisms')) or \
                    (root == os.path.join(crr_dir_opt, 'model')):
                #
                for f in files:
                    final_zip_fname = os.path.join(root, f)
                    foo.write(final_zip_fname, \
                            final_zip_fname.replace(fin_opt_folder, '', 1))

            if (root == os.path.join(crr_dir_opt, 'checkpoints')) or \
                    (root == os.path.join(crr_dir_opt, 'figures')):
                        final_zip_fold_name = os.path.join(root)
                        foo.write(final_zip_fold_name, \
                                final_zip_fold_name.replace(fin_opt_folder, '',
                                    1))

            if (root == crr_dir_opt):
                for f in files:
                    if f.endswith('.py') or (f.endswith('.sbatch') and hpc=="cscs-pizdaint"):
                        final_zip_fname = os.path.join(root, f)
                        foo.write(final_zip_fname, \
                            final_zip_fname.replace(fin_opt_folder, '', 1))
        foo.close()
        
    @classmethod
    def remove_files_from_opt_folder(cls, fin_dest_dir, hpc):
        """
        Remove unwanted files from the folder to be zipped
        """
        # 'nsg'
        if hpc == "nsg":
            for item in os.listdir(fin_dest_dir):
                if item.startswith('init') or item.endswith('.zip') \
                    or item.startswith('__MACOSX'):
                        os.remove(os.path.join(fin_dest_dir, item))
        # 'cscs-pizdaint'
        elif hpc == "cscs-pizdaint":
            for item in os.listdir(fin_dest_dir):
                if file.startswith("ipyparallel.sbatch") \
                    or file.startswith("zipfolder.py") \
                    or item.startswith('__MACOSX'):
                        os.remove(os.path.join(fin_dest_dir, item))

            


    @classmethod
    def add_exec_file(cls, hpc, fin_dest_dir="./", execname="fn", gennum=24, \
            offsize=12, mod_path="", joblaunchname="jln"):

        # Neuro Science Gateway
        if hpc == "nsg":
            with open(os.path.join(fin_dest_dir, execname),'w') as f:
                f.write('import os')
                f.write('\n')
                f.write('os.system(\'python opt_neuron.py --max_ngen=' + \
                        str(gennum) + ' --offspring_size=' + str(offsize) + \
                        ' --start --checkpoint ./checkpoints/checkpoint.pkl\')')
                f.write('\n')
            f.close()
            return execname

        # Juelich Jureca
        elif hpc == "jureca":
            with open(os.path.join(fin_dest_dir, execname),'w') as f:
                f.write("#!/bin/bash -x")
                f.write('\n')
                f.write('\n')
                f.write("set -e")
                f.write('\n')
                f.write("set -x")
                f.write('\n')
                f.write('\n')
                f.write("module purge all")
                f.write('\n')
                f.write("export  MODULEPATH=/homec/vsk25/vsk2501/local/jureca_booster-20180226142237/share/modules:$MODULEPATH")
                f.write('\n')
                f.write("module load bpopt")
                f.write('\n')
                f.write("export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}")
                f.write('\n')
                f.write('\n')
                f.write("OFFSPRING_SIZE=" + str(gennum))
                f.write('\n')
                f.write("MAX_NGEN=" + str(offsize))
                f.write('\n')
                f.write('\n')
                f.write("export USEIPYP=1")
                f.write('\n')
                f.write("export IPYTHONDIR=\"`pwd`/.ipython\"")
                f.write('\n')
                f.write("export IPYTHON_PROFILE=ipyparallel.${SLURM_JOBID}")
                f.write('\n')
                f.write("ipcontroller --init --sqlitedb --ip='*' --profile=${IPYTHON_PROFILE} &")
                f.write('\n')
                f.write("sleep 30")
                f.write('\n')
                f.write("srun ipengine --profile=${IPYTHON_PROFILE} &")
                f.write('\n')
                f.write('\n')
                f.write("CHECKPOINTS_DIR=\"checkpoints/run.${SLURM_JOBID}\"")
                f.write('\n')
                f.write("mkdir -p ${CHECKPOINTS_DIR}")
                f.write('\n')
                f.write('\n')
                f.write("pids=\"\"")
                f.write('\n')
                f.write("for seed in `seq 3 3`")
                f.write('\n')
                f.write("do")
                f.write('\n')
                f.write("    BLUEPYOPT_SEED=${seed} python opt_neuron.py --offspring_size=${OFFSPRING_SIZE} --max_ngen=${MAX_NGEN} --start --checkpoint \"${CHECKPOINTS_DIR}/seed${seed}.pkl\" &")
                f.write('\n')
                f.write("    pids=\"${pids} $!\"")
                f.write('\n')
                f.write("done")
                f.write('\n')
                f.write('\n')
                f.write("wait $pids")
                f.write('\n')
            f.close()

            # create sh for launching
            with open(os.path.join(fin_dest_dir, joblaunchname), 'w') as f:
                f.write("module purge all")
                f.write('\n')
                f.write("export MODULEPATH=" + mod_path + ":$MODULEPATH")
                f.write('\n')
                f.write("module load bpopt")
                f.write('\n')
                f.write("nrnivmodl ./mechanisms")
                f.write('\n')
                f.write("sbatch " + execname)
            f.close()
            return [execname, joblaunchname]

        # CSCS Pizdaint
        elif hpc == "cscs-pizdaint":
            with open(os.path.join(fin_dest_dir, execname),'w') as f:
                f.write('import os\n')
                f.write('import zipfile\n')
                f.write('retval = os.getcwd()\n')
                f.write('print "Current working directory %s" % retval\n')
                f.write('os.chdir(\'..\')\n')
                f.write('retval = os.getcwd()\n')
                f.write('print "Current working directory %s" % retval\n')
                f.write('def zipdir(path, ziph):\n')
                f.write('    for root, dirs, files in os.walk(path):\n')
                f.write('        for file in files:\n')
                f.write('            ziph.write(os.path.join(root, file))\n')
                f.write('zipf = zipfile.ZipFile(\'output.zip\', \'w\')\n')
                f.write('zipdir(\''+foldernameOPTstring+'/\', zipf)\n')
            f.close()

            # create file for launching job 
            with open(os.path.join(fin_dest_dir, joblaunchname), 'w') as f:
                f.write('#!/bin/bash -l\n')
                f.write('\n')
                f.write('#SBATCH --job-name=bluepyopt_ipyparallel\n')
                f.write('#SBATCH --error=logs/ipyparallel_%j.log\n')
                f.write('#SBATCH --output=logs/ipyparallel_%j.log\n')
                f.write('#SBATCH --partition=normal\n')
                f.write('#SBATCH --constraint=mc\n')
                f.write('\n')
                f.write('set -e\n')
                f.write('set -x\n')
                f.write('\n')
                f.write('export MODULEPATH=/users/bp000178/ich002/software/daint/'+\
                    'local-20181022101238/share/modules:$MODULEPATH;module load bpopt\n')
                f.write('\n')
                f.write('export USEIPYP=1\n')
                f.write('export IPYTHONDIR="`pwd`/.ipython"\n')
                f.write('export IPYTHON_PROFILE=ipyparallel.${SLURM_JOBID}\n')
                f.write('ipcontroller --init --sqlitedb --ip=\'*\' --profile=${IPYTHON_PROFILE} &\n')
                f.write('sleep 30\n')
                f.write('srun ipengine --profile=${IPYTHON_PROFILE} &\n')
                f.write('CHECKPOINTS_DIR="checkpoints"\n')
                f.write('nrnivmodl mechanisms\n')
                f.write('python opt_neuron.py --offspring_size='+OS.value+\
                    ' --max_ngen='+NGEN.value+' --start --checkpoint "${CHECKPOINTS_DIR}/checkpoint.pkl"\n') 
                f.write('python zipfolder.py')
                f.write('\n')
            f.close()

            return [execname, joblaunchname]

#
class OptSettings:
    params_default = {'wf_id': "", 'gennum': 2, 'offsize': 10, \
            'nodenum': 2, 'corenum': 1, 'runtime': 0.5, \
            'hpc_sys':  "", 'opt_sub_param_file': ""}

    @classmethod
    def get_params_default(cls):
        params = {
                'wf_id': cls.params_default["wf_id"], \
                'number_of_cores': cls.params_default["corenum"], \
                'number_of_nodes': cls.params_default["nodenum"], \
                'runtime': cls.params_default["runtime"], \
                'number_of_generations': cls.params_default["gennum"], \
                'offspring_size': cls.params_default["offsize"], \
                'hpc_sys': cls.params_default["hpc_sys"]
                }

        return params

    @classmethod
    def print_opt_params(cls, **kwargs):
        #
        if 'wf_id' in kwargs:
            wf_id = kwargs['wf_id']
        else:
            wf_id = cls.params_default['wf_id']

        #
        if 'gennum' in kwargs:
            gennum = kwargs['gennum']
        else:
            gennum = cls.params_default['gennum']

        #
        if 'offsize' in kwargs:
            offsize = kwargs['offsize']
        else:
            offsize = cls.params_default['offsize']

        #
        if 'nodenum' in kwargs:
            nodenum = kwargs['nodenum']
        else:
            nodenum = cls.params_default['nodenum']

        #
        if 'corenum' in kwargs:
            corenum = kwargs['corenum']
        else:
            corenum = cls.params_default['corenum']

        #
        if 'runtime' in kwargs:
            runtime = kwargs['runtime']
        else:
            runtime = cls.params_default['runtime']

        #
        if 'hpc_sys' in kwargs:
            hpc_sys = kwargs['hpc_sys']
        else:
            hpc_sys = cls.params_default['hpc_sys']

        #
        if 'opt_sub_param_file' in kwargs:
            opt_sub_param_file = kwargs['opt_sub_param_file']
        else:
            opt_sub_param_file = cls.params_default['opt_sub_param_file']

        

        params = {'wf_id':wf_id, 'number_of_cores': corenum, 'number_of_nodes': nodenum, \
                    'runtime': runtime, 'number_of_generations': gennum, \
                    'offspring_size': offsize, "hpc_sys": hpc_sys}

        with open(opt_sub_param_file, 'w') as pf:
            json.dump(params, pf)
        pf.close()
