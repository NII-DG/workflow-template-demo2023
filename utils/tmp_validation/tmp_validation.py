""" .tmp.validationフォルダ配下の操作クラス
"""

import os
import subprocess
import shutil
import json
from IPython.display import display, HTML, clear_output
import ipywidgets as widgets
import requests
from urllib import parse
import time
import logging
import re

TMP_VALIDATION_PATH = '.tmp/validation'
VALIDATION_RESULTS_PATH = 'validation_results'
RO_CRATE_FILE_NAME = 'ro_crate.json'
ENTITY_IDS_FILE_NAME = 'entity_ids.json'
RESULTS_FILE_NAME = 'results.json'
REQUEST_ID_FILE_NAME = 'request_id.txt'


def fetch_validation_result_path() -> str:
    """return TMP_VALIDATION_PATH
    RETURN
    -----------------
    VALIDATION_RESULTS_PATH : str
        Description : Path to a directory to temporarily store verification results.
    """
    return VALIDATION_RESULTS_PATH

def fetch_request_id_file_path() -> str:
    """return path to .tmp/validation/requestID.txt
    RETURN
    -----------------
    request_id_file_path : str
        Description : Path to the file that manages the Request ID issued by the Verification Service.
    """
    request_id_file_path = os.path.join(TMP_VALIDATION_PATH, REQUEST_ID_FILE_NAME)
    return request_id_file_path

def fetch_validation_results_file_path() -> str:
    """return path to .tmp/validation/{request_id}/{RESULTS_FILE_NAME}
    RETURN
    -----------------
    validation_results_file_path : str
        Description : path to .tmp/validation/{request_id}/{RESULTS_FILE_NAME}
    """
    validation_results_file_path = os.path.join(get_tmp_result_folder_path(), RESULTS_FILE_NAME)
    return validation_results_file_path

def get_tmp_result_folder_path():
    """return path to a directory to temporarily store verification results
    RETURN
    -----------------
    tmp_result_folder_path : str
        Description : path to a directory to temporarily store verification results
    """
    tmp_result_folder_path = os.path.join(TMP_VALIDATION_PATH, get_request_id())
    return tmp_result_folder_path

def save_request_id(request_id):
    """write the request ID
    RETURN
    -----------------
    """
    os.chdir(os.environ['HOME'])
    file_path = fetch_request_id_file_path()
    if not os.path.exists(TMP_VALIDATION_PATH):
        os.makedirs(TMP_VALIDATION_PATH)
    with open(file_path, 'w') as f:
        f.write(request_id)

def get_request_id():
    """get request ID
    RETURN
    -----------------
    request_id : str
        Description : Request ID obtained from the response of the verification request API
    """
    os.chdir(os.environ['HOME'])
    file_path = fetch_request_id_file_path()
    with open(file_path, 'r') as f:
        request_id = f.read()
    return request_id

def save_verification_results(result):
    """write the verification results in .tmp/validation/{request_id}
    RETURN
    -----------------
    """
    os.chdir(os.environ['HOME'])
    request_id = get_request_id()
    tmp_result_folder = get_tmp_result_folder_path()
    if not os.path.exists(tmp_result_folder):
        os.makedirs(tmp_result_folder)
    tmp_files = [
        [result['request']['roCrate'], os.path.join(tmp_result_folder, RO_CRATE_FILE_NAME)],
        [result['request']['entityIds'], os.path.join(tmp_result_folder, ENTITY_IDS_FILE_NAME)],
        [result['results'], os.path.join(tmp_result_folder, RESULTS_FILE_NAME)]
    ]
    for file in tmp_files:
        with open(file[1], 'w', encoding='utf-8') as f:
            json.dump(file[0], f, indent=4, ensure_ascii=False)

def operate_validation_results(need_sync):
    """If synchronizing verification results, move temporary verification results to VALIDATION_RESULTS_PATH and delete temporary verification-related files.
    If not synchronizing, delete the temporary validation-related files.
    RETURN
    -----------------
    """
    if need_sync == False:
        delete_verification_results_and_request_id()
    elif need_sync == True:
        src = get_tmp_result_folder_path()
        dst = VALIDATION_RESULTS_PATH
        if not os.path.exists(VALIDATION_RESULTS_PATH):
            os.makedirs(VALIDATION_RESULTS_PATH)
        for file in os.listdir(src):
            print(os.path.join(src, file))
            print(os.path.join(dst, file))
            shutil.copyfile(os.path.join(src, file), os.path.join(dst, file))

def delete_verification_results_and_request_id():
    """delete temporary validation-related files(.tmp/validation/{request_id}/*, .tmp/request_id.txt)
    RETURN
    -----------------
    """
    os.chdir(os.environ['HOME'])
    request_id = get_request_id()
    tmp_result_folder = get_tmp_result_folder_path()
    if os.path.exists(tmp_result_folder):
        shutil.rmtree(tmp_result_folder)
    request_id_file_path = fetch_request_id_file_path()
    if os.path.exists(request_id_file_path):
        os.remove(request_id_file_path)

def on_click_callback(clicked_button: widgets.Button) -> None:
    clear_output()
    print('検証結果の出力を削除しました。\n再度確認したい場合は、次のセルを実行する前にこのセルを再実行してください。')

def show_results():
    logging.error('検証の結果、メタデータに以下の不備が見つかりました。確認後、「確認を完了する」ボタンをクリックして次にお進みください。'\
                  '\n「確認を完了する」ボタンがクリックされていない場合は、検証結果を含んだこのノートブックがリポジトリに同期されます。')
    result_file_path = fetch_validation_results_file_path()
    # 検証結果を表示する
    with open ('/home/jovyan/' + result_file_path) as f:
        results_file = json.load(f)
    print(json.dumps(results_file, indent=2))
    for i in results_file:
        if 'Please check the log of the workflow execution using GET' in i['reason']:
            log_url = re.findall('http?://[\w/:%#\$&\?\(\)~\.=\+\-]+', i['reason'])[0]
            run_id = log_url.split('/')[-1]
            response = requests.get(log_url)
            log = response.json()
            print('\n========== ' + log_url + ' より取得した実行ログは以下です。==========\n')
            print(json.dumps(log, indent=2))
            # 実行ログをresults.jsonに追記する
            log_dict = {'workflow-log-' + run_id: log}
            save_dict = [results_file, log_dict]
            with open ('/home/jovyan/' + result_file_path, 'w') as f:
                json.dump(save_dict, f,indent=2)
                
    button = widgets.Button(description='確認を完了する')
    button.on_click(on_click_callback)
    display(button)

def get_validation_results():
    request_id = get_request_id()
    counter = 7
    while counter >0:
        try:
            # generate url_for_get_validation_results
            url_for_get_validation_results = parse.urlunparse((
                'http',
                'dg02.dg.rcos.nii.ac.jp:443', 
                request_id,
                '',
                '',
                ''
            ))
            # request get validation results
            response = requests.get(url_for_get_validation_results)
            result = response.json()
            counter -= 1
            clear_output()
        except Exception as e:
            logging.error('検証サービスに接続できません。')
            logging.error(str(e))
            break
        else:
            if response.status_code == requests.codes.ok:
                status = result['status']
                if status == 'UNKNOWN':
                    logging.error('リクエストID：' + request_id + 'の状況が読み込めませんでした。')
                    break
                elif any([status == 'QUEUED', status == 'RUNNING']):
                    print('リクエストID：' + request_id + 'は検証完了していません。時間をおいて再度確認します。')
                    time.sleep(10)
                    continue
                elif status == 'COMPLETE':
                    save_verification_results(result)
                    print('すべてのメタデータは適切に管理されています。次にお進みください。')
                    break
                elif status == 'FAILED':
                    save_verification_results(result)
                    show_results()
                    break
                elif status == 'EXECUTOR_ERROR':
                    logging.error('正常に検証を実行できませんでした。')
                    break
                elif status == 'CANCELING':
                    print('リクエストID：' + request_id + 'は現在キャンセル中です。')
                    break
                elif status == 'CANCELED':
                    print('リクエストID：' + request_id + 'はキャンセルされました。')
                    break

            elif response.ok == False:
                logging.error('異常が発生しました。担当者にお問い合わせください。')
                logging.error(result['message'])
                        
    else:
        clear_output()
        logging.error('検証に時間がかかっています。時間をおいて再度このセルを実行してください。')