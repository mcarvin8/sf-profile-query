"""
    Query Salesforce profiles in all orgs (Production/FullQA/Dev).
"""
from collections import OrderedDict
import csv
import logging
import subprocess
import sys

from colorama import init, Fore, Style

from get_salesforce_connection import get_salesforce_connection_alias

# Format logging message
logging.basicConfig(format='%(message)s', level=logging.DEBUG)
WARNING_COLOR = Fore.YELLOW
ERROR_COLOR = Fore.RED
COMMAND_COLOR = Fore.BLUE
SUCCESS_COLOR = Fore.GREEN


def query_org(org_name: str) -> OrderedDict:
    '''
    Query Salesforce records using alias for connection
    '''

    query = """
        SELECT
            Name,PermissionsCustomizeApplication,PermissionsModifyAllData,
            PermissionsAssignPermissionSets,PermissionsManageInternalUsers,
            PermissionsManagePasswordPolicies,PermissionsManageProfilesPermissionsets,
            PermissionsManageRoles,PermissionsManageSandboxes,PermissionsManageUsers,
            PermissionsInboundMigrationToolsUser,PermissionsOutboundMigrationToolsUser,
            PermissionsManageInteraction,PermissionsAuthorApex 
        FROM Profile WHERE Name LIKE '%SoD%' OR Name LIKE '%Release%'
    """

    sf = get_salesforce_connection_alias(alias=org_name)
    records = sf.query_all(query)['records']

    return records


def fetch_remote_data(relative_filepath: str, file_path: str) -> dict:
    '''
    Fetches remote data by restoring a file from a Git repository and reading its contents.
    '''

    subprocess.run(['git', 'restore', relative_filepath],
                   capture_output=True, text=True, check=True)
    remote_content = csv_to_dict(csv_file_path=file_path)

    return remote_content


def csv_to_dict(csv_file_path: str) -> list:
    '''
    Convert CSV file content to a list of dictionaries
    '''
    result_list = []
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        columns = next(reader)  # Read the first row for column names

        for data in reader:
            row_dict = dict(zip(columns, data))
            result_list.append(row_dict)

    return result_list


def convert_ordereddict_to_dict(obj: OrderedDict) -> dict:
    '''
    Convert OrderedDict to dict
    '''
    flat_dict = {}
    for key, value in obj.items():
        # Skip the 'type' and 'url' keys
        if key == 'attributes':
            continue
        if isinstance(value, bool):
            flat_dict[key] = str(value)
        elif isinstance(value, OrderedDict):
            nested_dict = convert_ordereddict_to_dict(value)
            flat_dict.update(nested_dict)
        else:
            flat_dict[key] = value

    return flat_dict


def compare_data(new_data: list, old_data: list) -> list:
    '''
    Compares two lists of dictionaries and identifies differences.
    '''
    differences = []

    # Assuming both lists have the same length, otherwise adjust as needed
    for new_item, old_item in zip(new_data, old_data):
        diff = {}
        all_keys = set(new_item.keys()).union(set(old_item.keys()))
        for key in all_keys:
            if str(new_item[key]).lower() != str(old_item[key]).lower():
                diff[key] = (new_item[key], old_item[key])
        if diff:
            differences.append(diff)

    return differences


def compare_permissions(list1, list2):
    '''
    Compares two lists of dictionaries and identifies differences.
    '''

    differences = []

    for dict1 in list1:
        for dict2 in list2:
            if dict1['Name'] == dict2['Name']:
                # Compare each key-value pair in the dictionaries
                for key in dict1:
                    if key != 'Name' and str(dict1[key]) != str(dict2[key]):
                        differences.append({'Name': dict1['Name'],'Permission': key,'Value in list1': dict1[key],'Value in list2': str(dict2[key])})
    
    return differences


def highlight_differences(differences: dict, org_name: str) -> None:
    '''
    highlight the difference of compared data
    '''

    for difference in differences:
        logging.info(ERROR_COLOR + "NOTE: The '%s' value for '%s' profile "
                "in the %s org has been changed from '%s' to '%s'" 
                + Style.RESET_ALL, difference['Permission'], difference['Name'],
                org_name.title(), difference['Value in list1'], difference['Value in list2'])


def main() -> None:
    '''
    1. Fetches remote data from <org>_Profiles.csv
    2. Queries ("prod","dev","fullqa") org latest records for profiles
    3. Compares remote data and recently fetched org data
    4. Highlight differences If any
    '''

    init(autoreset=True)
    changes_detected = False

    for org_name in ("prod","dev","fullqa"):

        file_name = org_name.title() + "_Profiles.csv"
        file_path = f"./profile_audits/{file_name}"
        relative_filepath = f"profile_audits/{file_name}"

        remote_data = fetch_remote_data(relative_filepath, file_path)

        records = query_org(org_name)

        if records:
            new_content = [{k: v for k, v in item.items() if k not in ['attributes']}
                           for item in records]

            differences = compare_permissions(new_content, remote_data)

            # differences = compare_data(new_content, remote_data)
        else:
            logging.info(WARNING_COLOR + 'WARNING: No entry found for %s org.'
                            + Style.RESET_ALL, org_name)

        if differences:
            changes_detected = True
            highlight_differences(differences, org_name.title())

        else:
            logging.info(SUCCESS_COLOR + "NOTE: No permission changed for all profiles "
                    "in the %s org" + Style.RESET_ALL, org_name.title())

    sys.exit(1 if changes_detected else 0)


if __name__ == '__main__':
    main()
