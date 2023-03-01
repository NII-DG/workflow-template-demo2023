import json
import os
import glob
from IPython.display import clear_output, HTML, display
from urllib import parse
import getpass
import requests
from http import HTTPStatus
from datalad import api
import traceback
import subprocess
from subprocess import PIPE



def fetch_param_file_path() -> str:
    return '/home/jovyan/WORKFLOWS/FLOW/param_files/params.json'


def fetch_monitoring_param_file_path() -> str:
    return '/home/jovyan/WORKFLOWS/FLOW/param_files/monitoring_params.json'


def verify_GIN_user():
    # 以下の認証の手順で用いる、
    # GINのドメイン名等をパラメタファイルから取得する
    params = {}
    with open(fetch_param_file_path(), mode='r') as f:
        params = json.load(f)

    # 正常に認証が終わるまで繰り返し
    global tokens
    global access_token
    clear_output()
    while True:
        print("GIN-forkのユーザー情報を入力後、Enterキーを押下してください。")
        name = input("ユーザー名：")
        password = getpass.getpass("パスワード：")
        email = input("メールアドレス：")
        clear_output()

        # GIN API Basic Authentication
        # refs: https://docs.python-requests.org/en/master/user/authentication/

        # 既存のトークンがあるか確認する
        baseURL = params['siblings']['ginHttp'] + '/api/v1/users/'
        response = requests.get(baseURL + name + '/tokens', auth=(name, password))
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            print("ユーザ名、またはパスワードが間違っています。\n恐れ入りますがもう一度ご入力ください。\n")
            continue

        tokens = response.json()
        if len(tokens) >= 1:
            access_token = response.json()[-1]
            clear_output()
            break
        elif len(tokens) < 1:
            # 既存のトークンがなければ作成する
            response = requests.post(baseURL + name + '/tokens', data={"name": "system-generated"}, auth=(name, password))
            if response.status_code == HTTPStatus.CREATED:
                access_token = response.json()
                clear_output()
                break
    return tokens, access_token, name, email


def fetch_ssh_config_path():
    ssh_config_path = '/home/jovyan/.ssh/config'
    return ssh_config_path


def config_mdx(name_mdx, mdxDomain):
    # mdx接続情報を設定ファイルに反映させる
    path = fetch_ssh_config_path()
    s = ''

    if os.path.exists(path):
        # 設定ファイルがある場合
        with open(path, "r") as f:
            s = f.read()

        # mdxの設定があれば該当部分のみ削除して設定を新たに追記する
        if s.find('Host mdx') == -1:
            # mdxの設定が無ければ追記する
            write_mdx_config(mode='a', mdxDomain=mdxDomain, name_mdx=name_mdx)

        else:
            # mdxの設定があれば該当部分のみ削除して設定を新たに追記する
            front = s[:s.find('Host mdx')]
            front = front.rstrip()
            find_words = 'IdentityFile ~/.ssh/id_rsa\n\tStrictHostKeyChecking no'
            back = s[(s.find(find_words) + len(find_words)):]
            back = back.strip()
            if len(back) >= 1:
                s = front + '\n' + back + '\n'
            elif len(front) <= 0:
                s = front
            else:
                s = front + '\n'
            with open(path, 'w') as f:
                f.write(s)
            write_mdx_config(mode='a', mdxDomain=mdxDomain, name_mdx=name_mdx)
    else:
        # 設定ファイルが無い場合、新規作成して新たに書き込む
        write_mdx_config(mode='w', mdxDomain=mdxDomain, name_mdx=name_mdx)


def write_mdx_config(mode, mdxDomain, name_mdx):
    path = fetch_ssh_config_path()
    with open(path, mode) as f:
        f.write('\nHost mdx\n')
        f.write('\tHostname ' + mdxDomain + '\n')
        f.write('\tUser ' + name_mdx + '\n')
        f.write('\tPort 22\n')
        f.write('\tIdentityFile ~/.ssh/id_rsa\n')
        f.write('\tStrictHostKeyChecking no\n')


def config_GIN(ginHttp):
    """リポジトリホスティングサーバのURLからドメイン名を抽出してコンテナに対してSHH通信を信頼させるメソッド
        この時、/home/jovyan/.ssh/configファイルに設定値を出力する。
    ARG
    ---------------------------
    ginHttp : str
        Description : リポジトリホスティングサーバのURL ex : http://dg01.dg.rcos.nii.ac.jp
    """
    # SSHホスト（＝GIN）を信頼する設定
    path = fetch_ssh_config_path()
    s = ''
    pr = parse.urlparse(ginHttp)
    ginDomain = pr.netloc
    if os.path.exists(path):
        with open(path, 'r') as f:
            s = f.read()
        if s.find('host ' + ginDomain + '\n\tStrictHostKeyChecking no\n\tUserKnownHostsFile=/dev/null') == -1:
            # 設定が無い場合は追記する
            with open('/home/jovyan/.ssh/config', mode='a') as f:
                write_GIN_config(mode='a', ginDomain=ginDomain)
        else:
            # すでにGINを信頼する設定があれば何もしない
            pass
    else:
        # 設定ファイルが無い場合は新規作成して設定を書きこむ
        with open('/home/jovyan/.ssh/config', mode='w') as f:
            write_GIN_config(mode='w', ginDomain=ginDomain)


def write_GIN_config(mode, ginDomain):
    path = fetch_ssh_config_path()
    with open(path, mode) as f:
        f.write('\nhost ' + ginDomain + '\n')
        f.write('\tStrictHostKeyChecking no\n')
        f.write('\tUserKnownHostsFile=/dev/null\n')


def fetch_files(dir_path):
    """引数に与えたディレクトリパス以下にあるファイルのリストを作成して返す"""
    data_list = []
    files = glob.glob(dir_path + "/*")
    for f in files:
        data_list += [f]
    return data_list


def update_repo_url():
    # HTTPとSSHのリモートURLを最新化する
    # APIリクエストに必要な情報を取得する
    params = {}
    with open(fetch_param_file_path(), mode='r') as f:
        params = json.load(f)
    os.chdir(os.environ['HOME'])
    file_path = '.repository_id'
    f = open(file_path, 'r')
    repo_id = f.read()
    f.close()

    # APIからリポジトリの最新のSSHのリモートURLを取得し、リモート設定を更新する
    request_url = params['siblings']['ginHttp'] + '/api/v1/repos/search?id=' + repo_id
    res = requests.get(request_url)
    res_data = res.json()
    ssh_url = res_data['data'][0]['ssh_url']
    http_url = res_data['data'][0]['html_url'] + '.git'
    update_list = [['gin', ssh_url],['origin', http_url]]
    for update_target in update_list:
        result = subprocess.run('git remote set-url ' + update_target[0] + ' ' + update_target[1], shell=True, stdout=PIPE, stderr=PIPE, text=True)
        if 'No such remote' in result.stderr:
            subprocess.run('git remote add ' + update_target[0] + ' ' + update_target[1], shell=True)

        
DATALAD_MESSAGE = ''
DATALAD_ERROR = ''
CONNECT_REPO_ERROR = 'リポジトリに接続できません。リポジトリが存在しているか確認してください。'
CONFLICT_ERROR = 'リポジトリ側の変更と競合しました。競合を解決してください。'
PUSH_ERROR = 'リポジトリへの同期に失敗しました。'
SUCCESS = 'データ同期が完了しました。'
SIBLING = 'gin'

# リポジトリと同期する
def syncs_with_repo(git_path, gitannex_path, message):
    datalad_message = ''
    datalad_error = ''
    try:
        # lock状態でないとS3データが同期されてしまう
        os.chdir(os.environ['HOME'])
        os.system('git annex lock')
        save(git_path, gitannex_path, message)
        update()
    except:
        datalad_error = traceback.format_exc()
        # リモートへの接続エラーが発生している場合は回復を試す
        if 'Repository does not exist:' in datalad_error:
            try:
                # リモートリポジトリのURLを最新化する
                update_repo_url()
            except:
                # リポジトリ自体が無いときなど
                datalad_message = CONNECT_REPO_ERROR
            else:
                datalad_error = ''
                try:
                    update()
                except:
                    datalad_error = traceback.format_exc()
                    datalad_message = CONFLICT_ERROR
                else:
                    try:
                        push()
                    except:
                        datalad_error = traceback.format_exc()
                        datalad_message = PUSH_ERROR
                    else:
                        os.chdir(os.environ['HOME'])
                        os.system('git annex unlock')
                        datalad_message = SUCCESS
        else:
            datalad_message = CONFLICT_ERROR
    else:
        try:
            push()
        except:
            datalad_error = traceback.format_exc()
            datalad_message = PUSH_ERROR
        else:
            os.chdir(os.environ['HOME'])
            os.system('git annex unlock')
            datalad_message = SUCCESS
    finally:
        clear_output()
        display(HTML("<p>" + datalad_message + "</p>"))
        display(HTML("<p><font color='red'>" + datalad_error + "</font></p>"))

def save(git_path, gitannex_path, message):
    if gitannex_path != None:
        api.save(message=message + ' (git-annex)', path=gitannex_path)
    if git_path != None:
        api.save(message=message + ' (git)', path=git_path, to_git=True)

def update():
    api.update(sibling=SIBLING, how='merge')

def push():
    api.push(to=SIBLING, data='auto')


# 研究名と実験名を表示する関数
def show_name(color='black', EXPERIMENT_TITLE=None):
    # リモートリポジトリのURLを最新化する
    update_repo_url()
    os.chdir(os.environ['HOME'])

    # 研究リポジトリ名表示
    RESEARCH_TITLE = subprocess.getoutput('git config --get remote.origin.url').split('/')[-1].replace('.git', '')
    res_text = "<h1 style='color:" + color + "'>研究リポジトリ名：" + RESEARCH_TITLE + "</h1>" 
    clear_output()
    display(HTML(res_text))
    
    if EXPERIMENT_TITLE is not None:
        #実験パッケージ名表示
        exp_text = "<h1 style='color:" + color + "'>実験パッケージ名：" + EXPERIMENT_TITLE + "</h1>" 
        display(HTML(exp_text))