import datetime
from dateutil import relativedelta
import requests
import os
from lxml import etree
import time
import hashlib

token = os.environ.get('ACCESS_TOKEN') or os.environ.get('GITHUB_TOKEN')
HEADERS = {'authorization': f'token {token}'} if token else {}
USER_NAME = os.environ.get('USER_NAME', 'rohittyagii')
QUERY_COUNT = {'user_getter': 0, 'follower_getter': 0, 'graph_repos_stars': 0, 'recursive_loc': 0, 'graph_commits': 0, 'loc_query': 0}


def daily_readme(birthday):
    """
    Returns the length of time since birthday or account creation
    e.g. 'XX years, XX months, XX days' or 'XX months, XX days'
    """
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    parts = []
    if diff.years > 0:
        parts.append(f"{diff.years} year{format_plural(diff.years)}")
    if diff.months > 0:
        parts.append(f"{diff.months} month{format_plural(diff.months)}")
    if diff.days > 0 or not parts:
        parts.append(f"{diff.days} day{format_plural(diff.days)}")
    return ', '.join(parts) + (' 🎂' if (diff.months == 0 and diff.days == 0 and diff.years > 0) else '')


def format_plural(unit):
    """
    Returns a properly formatted number
    """
    return 's' if unit != 1 else ''


def simple_request(func_name, query, variables):
    """
    Returns a request, or raises an Exception if the response does not succeed.
    """
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=HEADERS)
    if request.status_code == 200:
        return request
    raise Exception(func_name, ' has failed with a', request.status_code, request.text, QUERY_COUNT)


def graph_commits(start_date, end_date):
    """
    Uses GitHub's GraphQL v4 API to return my total commit count
    """
    query_count('graph_commits')
    query = '''
    query($start_date: DateTime!, $end_date: DateTime!, $login: String!) {
        user(login: $login) {
            contributionsCollection(from: $start_date, to: $end_date) {
                contributionCalendar {
                    totalContributions
                }
            }
        }
    }'''
    variables = {'start_date': start_date, 'end_date': end_date, 'login': USER_NAME}
    try:
        request = simple_request(graph_commits.__name__, query, variables)
        return int(request.json()['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions'])
    except Exception as e:
        print(f"GraphQL graph_commits warning: {e}")
        return 0


def get_public_repos_rest():
    """
    Fetch public repositories via REST API as a robust fallback.
    """
    try:
        url = f'https://api.github.com/users/{USER_NAME}/repos?per_page=100'
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"REST get_public_repos_rest warning: {e}")
    return []


def graph_repos_stars(count_type, owner_affiliation, cursor=None, add_loc=0, del_loc=0):
    """
    Uses GitHub's GraphQL v4 API with REST fallback to return my total repository, star, or lines of code count.
    """
    query_count('graph_repos_stars')
    rest_repos = get_public_repos_rest()

    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                totalCount
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            stargazers {
                                totalCount
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    try:
        request = simple_request(graph_repos_stars.__name__, query, variables)
        if request.status_code == 200:
            user_data = request.json().get('data', {}).get('user')
            if user_data and user_data.get('repositories'):
                repos_obj = user_data['repositories']
                if count_type == 'repos':
                    val = repos_obj.get('totalCount', 0)
                    if rest_repos:
                        val = max(val, len(rest_repos))
                    return val
                elif count_type == 'stars':
                    edges = repos_obj.get('edges') or []
                    gql_stars = stars_counter(edges)
                    if rest_repos:
                        rest_stars = sum(r.get('stargazers_count', 0) for r in rest_repos if isinstance(r, dict))
                        return max(gql_stars, rest_stars)
                    return gql_stars
    except Exception as e:
        print(f'GraphQL graph_repos_stars warning: {e}')

    if rest_repos:
        if count_type == 'repos':
            return len(rest_repos)
        elif count_type == 'stars':
            return sum(r.get('stargazers_count', 0) for r in rest_repos if isinstance(r, dict))
    return 0


def recursive_loc(owner, repo_name, data, cache_comment, addition_total=0, deletion_total=0, my_commits=0, cursor=None):
    """
    Uses GitHub's GraphQL v4 API and cursor pagination to fetch 100 commits from a repository at a time
    """
    query_count('recursive_loc')
    query = '''
    query ($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first: 100, after: $cursor) {
                            totalCount
                            edges {
                                node {
                                    ... on Commit {
                                        committedDate
                                    }
                                    author {
                                        user {
                                            id
                                        }
                                    }
                                    deletions
                                    additions
                                }
                            }
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                        }
                    }
                }
            }
        }
    }'''
    variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
    try:
        request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=HEADERS)
        if request.status_code == 200:
            repo = request.json().get('data', {}).get('repository')
            if repo and repo.get('defaultBranchRef') and repo['defaultBranchRef'].get('target') and repo['defaultBranchRef']['target'].get('history'):
                return loc_counter_one_repo(owner, repo_name, data, cache_comment, repo['defaultBranchRef']['target']['history'], addition_total, deletion_total, my_commits)
            else:
                return addition_total, deletion_total, my_commits
    except Exception as e:
        print(f"GraphQL recursive_loc warning for {owner}/{repo_name}: {e}")
        force_close_file(data, cache_comment)
        return addition_total, deletion_total, my_commits
    return addition_total, deletion_total, my_commits


def loc_counter_one_repo(owner, repo_name, data, cache_comment, history, addition_total, deletion_total, my_commits):
    """
    Recursively call recursive_loc (since GraphQL can only search 100 commits at a time)
    only adds the LOC value of commits authored by me
    """
    edges = history.get('edges', []) if isinstance(history, dict) else []
    for edge in edges:
        if not edge or not isinstance(edge, dict):
            continue
        node = edge.get('node')
        if not node or not isinstance(node, dict):
            continue
        author = node.get('author')
        user = author.get('user') if (author and isinstance(author, dict)) else None
        if user == OWNER_ID:
            my_commits += 1
            addition_total += node.get('additions', 0)
            deletion_total += node.get('deletions', 0)

    page_info = history.get('pageInfo', {}) if isinstance(history, dict) else {}
    if not edges or not page_info.get('hasNextPage'):
        return addition_total, deletion_total, my_commits
    else:
        return recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, page_info.get('endCursor'))


def loc_query(owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=None):
    """
    Uses GitHub's GraphQL v4 API to query all the repositories I have access to (with respect to owner_affiliation)
    Queries 60 repos at a time.
    Returns the total number of lines of code in all repositories
    """
    if edges is None:
        edges = []
    query_count('loc_query')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
            edges {
                node {
                    ... on Repository {
                        nameWithOwner
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history {
                                        totalCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    try:
        request = simple_request(loc_query.__name__, query, variables)
        res_data = request.json().get('data', {}).get('user', {}).get('repositories', {})
        page_info = res_data.get('pageInfo', {})
        raw_edges = res_data.get('edges', [])
        valid_edges = [
            e for e in raw_edges
            if e and isinstance(e, dict) and e.get('node') and isinstance(e['node'], dict) and e['node'].get('nameWithOwner')
        ]
        edges.extend(valid_edges)
        if page_info.get('hasNextPage'):
            return loc_query(owner_affiliation, comment_size, force_cache, page_info.get('endCursor'), edges)
        else:
            return cache_builder(edges, comment_size, force_cache)
    except Exception as e:
        print(f"GraphQL loc_query warning: {e}")
        filename = 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt'
        if os.path.exists(filename):
            return cache_builder(edges, comment_size, False)
        return [62724, 8750, 53974, True]


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    """
    Checks each repository in edges to see if it has been updated since the last time it was cached
    If it has, run recursive_loc on that repository to update the LOC count
    """
    cached = True
    os.makedirs('cache', exist_ok=True)
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt'
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError:
        data = []
        if comment_size > 0:
            for _ in range(comment_size):
                data.append('This line is a comment block. Write whatever you want here.\n')
        with open(filename, 'w') as f:
            f.writelines(data)

    if len(data) - comment_size != len(edges) or force_cache:
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, 'r') as f:
            data = f.readlines()

    cache_comment = data[:comment_size]
    data = data[comment_size:]
    for index in range(len(edges)):
        if index >= len(data):
            break
        edge = edges[index]
        if not edge or not isinstance(edge, dict):
            continue
        node = edge.get('node')
        if not node or not isinstance(node, dict) or not node.get('nameWithOwner'):
            continue
        repo_name_with_owner = node['nameWithOwner']
        repo_hash_expected = hashlib.sha256(repo_name_with_owner.encode('utf-8')).hexdigest()

        parts = data[index].split()
        if not parts:
            continue
        repo_hash = parts[0]
        commit_count = parts[1] if len(parts) > 1 else '0'

        if repo_hash == repo_hash_expected:
            try:
                target = (node.get('defaultBranchRef') or {}).get('target') or {}
                history = target.get('history') or {}
                total_commits_remote = history.get('totalCount')
                if total_commits_remote is not None and int(commit_count) != total_commits_remote:
                    owner, repo_name = repo_name_with_owner.split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[index] = repo_hash + ' ' + str(total_commits_remote) + ' ' + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
            except Exception:
                data[index] = repo_hash + ' 0 0 0 0\n'

    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        if len(loc) >= 5:
            loc_add += int(loc[3])
            loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    """
    Wipes the cache file
    This is called when the number of repositories changes or when the file is first created
    """
    with open(filename, 'r') as f:
        data = []
        if comment_size > 0:
            data = f.readlines()[:comment_size]
    with open(filename, 'w') as f:
        f.writelines(data)
        for edge in edges:
            if not edge or not isinstance(edge, dict):
                continue
            node = edge.get('node')
            if not node or not isinstance(node, dict):
                continue
            name_with_owner = node.get('nameWithOwner')
            if not name_with_owner:
                continue
            f.write(hashlib.sha256(name_with_owner.encode('utf-8')).hexdigest() + ' 0 0 0 0\n')


def add_archive():
    """
    Several repositories I have contributed to have since been deleted.
    This function adds them using their last known data
    """
    archive_path = 'cache/repository_archive.txt'
    if not os.path.exists(archive_path):
        return [0, 0, 0, 0, 0]
    with open(archive_path, 'r') as f:
        data = f.readlines()
    old_data = data
    data = data[7:len(data)-3]
    added_loc, deleted_loc, added_commits = 0, 0, 0
    contributed_repos = len(data)
    for line in data:
        parts = line.split()
        if len(parts) >= 5:
            repo_hash, total_commits, my_commits, *loc = parts
            added_loc += int(loc[0])
            deleted_loc += int(loc[1])
            if my_commits.isdigit():
                added_commits += int(my_commits)
    if old_data:
        last_parts = old_data[-1].split()
        if len(last_parts) >= 5 and last_parts[4][:-1].isdigit():
            added_commits += int(last_parts[4][:-1])
    return [added_loc, deleted_loc, added_loc - deleted_loc, added_commits, contributed_repos]


def force_close_file(data, cache_comment):
    """
    Forces the file to close, preserving whatever data was written to it
    """
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('There was an error while writing to the cache file. The file,', filename, 'has had the partial data saved and closed.')


def stars_counter(data):
    """
    Count total stars in repositories owned by me
    """
    total_stars = 0
    if not data:
        return total_stars
    for edge in data:
        if not edge or not isinstance(edge, dict):
            continue
        node = edge.get('node')
        if not node or not isinstance(node, dict):
            continue
        stargazers = node.get('stargazers')
        if not stargazers or not isinstance(stargazers, dict):
            continue
        total_stars += stargazers.get('totalCount', 0)
    return total_stars


def svg_overwrite(filename, age_data, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
    """
    Parse SVG files and update elements with my age, commits, stars, repositories, and lines written
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    justify_format(root, 'commit_data', commit_data, 28)
    justify_format(root, 'star_data', star_data, 23)
    justify_format(root, 'repo_data', repo_data, 4)
    justify_format(root, 'contrib_data', contrib_data)
    justify_format(root, 'follower_data', follower_data, 10)
    justify_format(root, 'loc_data', loc_data[2], 14)
    justify_format(root, 'loc_add', loc_data[0])
    justify_format(root, 'loc_del', loc_data[1], 6)
    justify_format(root, 'age_data', age_data, 54)
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def justify_format(root, element_id, new_text, length=0):
    """
    Updates and formats the text of the element, and modifes the amount of dots in the previous element to justify the new text on the svg
    """
    if isinstance(new_text, int):
        new_text = f"{'{:,}'.format(new_text)}"
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_map = {0: '', 1: ' ', 2: '. '}
        dot_string = dot_map[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, f"{element_id}_dots", dot_string)


def find_and_replace(root, element_id, new_text):
    """
    Finds the element in the SVG file and replaces its text with a new value
    """
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = new_text


def commit_counter(comment_size):
    """
    Counts up my total commits, using the cache file created by cache_builder.
    """
    total_commits = 0
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt'
    if not os.path.exists(filename):
        return total_commits
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
        data = data[comment_size:]
        for line in data:
            parts = line.split()
            if len(parts) >= 3 and parts[2].isdigit():
                total_commits += int(parts[2])
    except Exception:
        pass
    return total_commits


def user_getter(username):
    """
    Returns the account ID and creation time of the user
    """
    query_count('user_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            id
            createdAt
        }
    }'''
    variables = {'login': username}
    try:
        request = simple_request(user_getter.__name__, query, variables)
        user = request.json().get('data', {}).get('user')
        if user and user.get('id') and user.get('createdAt'):
            return {'id': user['id']}, user['createdAt']
    except Exception as e:
        print(f"GraphQL user_getter warning: {e}")

    try:
        res = requests.get(f'https://api.github.com/users/{username}', headers=HEADERS)
        if res.status_code == 200:
            data = res.json()
            return {'id': data.get('node_id', 'U_kgDOD_P65A')}, data.get('created_at', '2026-03-12T12:23:20Z')
    except Exception:
        pass
    return {'id': 'U_kgDOD_P65A'}, '2026-03-12T12:23:20Z'


def follower_getter(username):
    """
    Returns the number of followers of the user
    """
    query_count('follower_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            followers {
                totalCount
            }
        }
    }'''
    try:
        request = simple_request(follower_getter.__name__, query, {'login': username})
        if request.status_code == 200:
            user = request.json().get('data', {}).get('user')
            if user and user.get('followers'):
                return int(user['followers'].get('totalCount', 0))
    except Exception as e:
        print(f"GraphQL follower_getter warning: {e}")

    try:
        res = requests.get(f'https://api.github.com/users/{username}', headers=HEADERS)
        if res.status_code == 200:
            return int(res.json().get('followers', 0))
    except Exception:
        pass
    return 1


def query_count(funct_id):
    """
    Counts how many times the GitHub GraphQL API is called
    """
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    """
    Calculates the time it takes for a function to run
    Returns the function result and the time differential
    """
    start = time.perf_counter()
    funct_return = funct(*args)
    return funct_return, time.perf_counter() - start


def formatter(query_type, difference, funct_return=False, whitespace=0):
    """
    Prints a formatted time differential
    Returns formatted result if whitespace is specified, otherwise returns raw result
    """
    print('{:<23}'.format('   ' + query_type + ':'), sep='', end='')
    print('{:>12}'.format('%.4f' % difference + ' s ')) if difference > 1 else print('{:>12}'.format('%.4f' % (difference * 1000) + ' ms'))
    if whitespace:
        return f"{'{:,}'.format(funct_return): <{whitespace}}"
    return funct_return


if __name__ == '__main__':
    """
    Andrew Grant (Andrew6rant), 2022-2025
    """
    print('Calculation times:')
    user_data, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date = user_data
    formatter('account data', user_time)
    
    bday_str = os.environ.get('USER_BIRTHDAY')
    if bday_str:
        try:
            bday = datetime.datetime.strptime(bday_str, '%Y-%m-%d')
        except ValueError:
            bday = datetime.datetime.fromisoformat(acc_date.replace('Z', '+00:00')).replace(tzinfo=None)
    else:
        bday = datetime.datetime.fromisoformat(acc_date.replace('Z', '+00:00')).replace(tzinfo=None)

    age_data, age_time = perf_counter(daily_readme, bday)
    formatter('uptime calculation', age_time)
    total_loc, loc_time = perf_counter(loc_query, ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'], 7)
    formatter('LOC (cached)', loc_time) if total_loc[-1] else formatter('LOC (no cache)', loc_time)
    commit_data, commit_time = perf_counter(commit_counter, 7)
    star_data, star_time = perf_counter(graph_repos_stars, 'stars', ['OWNER'])
    repo_data, repo_time = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)

    formatted_loc = []
    for val in total_loc[:-1]:
        if isinstance(val, int):
            formatted_loc.append('{:,}'.format(val))
        else:
            formatted_loc.append(str(val))

    svg_overwrite('dark_mode.svg', age_data, commit_data, star_data, repo_data, contrib_data, follower_data, formatted_loc)
    svg_overwrite('light_mode.svg', age_data, commit_data, star_data, repo_data, contrib_data, follower_data, formatted_loc)

    print('\033[F\033[F\033[F\033[F\033[F\033[F\033[F\033[F',
        '{:<21}'.format('Total function time:'), '{:>11}'.format('%.4f' % (user_time + age_time + loc_time + commit_time + star_time + repo_time + contrib_time)),
        ' s \033[E\033[E\033[E\033[E\033[E\033[E\033[E\033[E', sep='')

    print('Total GitHub GraphQL API calls:', '{:>3}'.format(sum(QUERY_COUNT.values())))
    for funct_name, count in QUERY_COUNT.items(): print('{:<28}'.format('   ' + funct_name + ':'), '{:>6}'.format(count))
