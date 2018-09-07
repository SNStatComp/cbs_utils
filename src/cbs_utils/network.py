# -*- coding: utf-8 -*-
import win32com.client
from typing import Dict, List


class ActiveDirectory(object):
    """
    Active Directory representation.
    This object is intended to have all functionality that one would normally want/have from an Active Directory.
    """

    ## The values of default groups should be the groups you wish to examine, use the group's sAMAccountName
    default_groups = ['Administrators', 'Account Operators', 'Backup Operators',
                      'Server Operators', 'DnsAdmins', 'Domain Admins',
                      'Exchange Administrators', 'Exchange Services',
                      'DHCP Administrators']
    default_attrs = ['name', 'member', 'objectClass', 'adspath',
                     'primaryGroupToken', 'primaryGroupID']

    def __init__(self, server: str = None):
        """
        Creates an Active Directory object
        :param server: Alternative Server to use
        """
        # TYPE: (str)->object
        self.server = server
        # if the server is given
        if self.server:
            # use this server
            self.ldap_root = win32com.client.GetObject('LDAP://{server}/rootDSE'.format(server=self.server))
        else:
            # else use the default
            self.ldap_root = win32com.client.GetObject('LDAP://rootDSE')
        # retrieve the ldap location
        self.ldap_loc = self.ldap_root.Get('defaultNamingContext')
        # get the connection object
        self.objConnection = win32com.client.Dispatch("ADODB.Connection")
        # open the connection
        self.objConnection.Open("Provider=ADsDSOObject")

    def get_group_info(self, name, searchRoot: str = None,
                       category: str = "Group",
                       attributes: list = None) -> Dict[str, str]:
        """
        Obtain the group information for the given name
        :param name: profile name
        :param searchRoot: where to start looking
        :param category: what category to look in (by default the Group)
        :param attributes: additional attributes, examples are 'name', 'member', 'objectClass'
        :return: A Field : Value dictionary of all found information
        """
        if not searchRoot:
            searchRoot = self.ldap_loc
        if not attributes:
            attributes = self.default_attrs
        # create the search string
        strSearch = \
            "<LDAP://{search_root}>;(&(objectCategory={category})\
            (sAMAccountName={name}));{attrs};subtree".format(search_root=searchRoot,
                                                             category=category,
                                                             name=name,
                                                             attrs=','.join(attributes))
        # execute the search
        objRecordSet = self.objConnection.Execute(strSearch)[0]
        objRecord = dict()
        # Normally, we would only expect one object to be retrieved.
        if objRecordSet.RecordCount == 1:
            # Set up a dictionary with attribute/value pairs and return the dictionary.
            for f in objRecordSet.Fields:
                objRecord[f.Name] = f.Value
        return objRecord

    def get_group_members(self, strLdap: str,
                          attributes: list = None) -> List[Dict[str,object]]:
        """
        Look up a group's members.
        :param strLdap: groups adspath attribute.
        :param attributes: attributes to append to the search query
        :return: List of dictionaries, each dictionary item has a name and indicator of whether it is a group.
        """
        if not attributes:
            attributes = self.default_attrs
        strSearch = "<%s>;;%s" % (strLdap, ','.join(attributes))
        objRecordSet = self.objConnection.Execute(strSearch)[0]
        objRecord = dict()
        memberList = []

        # Normally, we would only expect one object to be retrieved.
        if objRecordSet.RecordCount == 1:
            for f in objRecordSet.Fields:
                objRecord[f.Name] = f.Value

            # Check to see if the group has any members
            if objRecord['member'] is not None:
                # Look up each member and get their LDAP object
                for mbr in objRecord['member']:
                    objRS = self.objConnection.Execute("<LDAP://%s>;;name,objectClass,adspath" % mbr)[0]
                    # Check to see if the member is a group.
                    is_group = True if 'group' in objRS.Fields[1].Value else False
                    # append the name and group indicator to the answers
                    memberList.append({"name": objRS.Fields[0].Value, "is_group":is_group})
        # Return the list of results
        return memberList

    def get_member_info(self, member: str, strLdap: str = None,
                        attributes: List[str] = None) -> Dict[str, str]:
        """
        Returns user info. If there is no list of attributes given, it will use
        a default list (for testing purposes).
        """
        searchRoot = strLdap if strLdap else self.ldap_loc
        attrs = attributes if attributes else self.default_attrs
        strSearch = \
            "<LDAP://{search_root}>;(&(objectCategory=user)\
            (sAMAccountName={name}));{attrs};subtree".format(search_root=searchRoot,
                                                             name=member,
                                                             attrs=','.join(attrs))
        # execute the search
        objRecordSet = self.objConnection.Execute(strSearch)[0]
        objRecord = dict()
        # Normally, we would only expect one object to be retrieved.
        if objRecordSet.RecordCount == 1:
            # Set up a dictionary with attribute/value pairs and return the dictionary.
            for f in objRecordSet.Fields:
                objRecord[f.Name] = f.Value
        return objRecord

    def get_primary_group(self, token, searchRoot: str = None, header="   "):
        """ Used to look up Users whose Primary Group is set to one of the groups we're
        looking up.  This is necessary as AD uses that attribute to calculate a group's
        membership.  These type of users do not show up if you query the group's member field
        directly.

        searchRoot is the part of the LDAP tree that you want to start searching from.
        token is the groups primaryGroupToken.
        """
        if not searchRoot:
            searchRoot = self.ldap_loc
        strSearch = \
            "<LDAP://%s>;(primaryGroupID=%d);name;subtree" % \
            (searchRoot, token)
        objRecordSet = self.objConnection.Execute(strSearch)[0]
        memberList = []

        # Process if accounts are found.
        if objRecordSet.RecordCount > 0:
            memberList.append("Primary Group calculated:")
            objRecordSet.MoveFirst()

            while not objRecordSet.EOF:
                memberList.append("%s%s" % (header, objRecordSet.Fields[0].Value))
                objRecordSet.MoveNext()

        # Return the list of results
        return memberList


if __name__ == '__main__':
    import sys
    server = None if len(sys.argv) == 1 else sys.argv[1]

    ad = ActiveDirectory(server)
    # for getting groups in the active directory:
    message = []
    for group in ad.default_groups:
        objGrp = ad.get_group_info(group)
        if objGrp:
            message.append("\nMembers of %s:" % objGrp['name'])
            group_members = ad.get_group_members(objGrp['adspath'])
            for member in group_members:
                message.append("is_group: {}, name: {}".format(member['is_group'], member['name']))
            message.extend(ad.get_primary_group(objGrp['primaryGroupToken']))

    # for requesting user info, the attributes are the standard ones from the list.
    t = ad.get_member_info(member='<PID>', attributes=["objectGuid", "sAMAccountName", "memberOf", "displayName",
                                                      "userPrincipalName", "proxyAddresses", "givenName", "sn",
                                                      "initials", "pwdlastset", "userAccountControl", "mail",
                                                      "distinguishedName", "objectclass", "employeeID",
                                                      "employeeNumber", "employeeType", "title", "division",
                                                      "department", "businessCategory", "l", "telephoneNumber",
                                                      "physicalDeliveryOfficeName", "manager"])
    print(t)
    print("\n".join(message))