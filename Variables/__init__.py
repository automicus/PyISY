from datetime import datetime
from time import sleep
from .variable import Variable
from xml.dom import minidom


class Variables(object):

    vids = []
    vnames = []
    vobjs = []
    vtypes = []

    def __init__(self, parent, root=None, vids=None, vnames=None,
                 vobjs=None, vtypes=None, xml=None):
        self.parent = parent
        self.root = root

        if vids is not None and vnames is not None \
                and vobjs is not None and vtypes is not None:
            self.vids = vids
            self.vnames = vnames
            self.vobjs = vobjs
            self.vtypes = vtypes

        elif xml is not None:
            self.parse(xml)

    def __str__(self):
        if self.root is None:
            return 'Variable Collection'
        elif self.root == 1:
            return 'Variable Collection (Type: ' + str(self.root) + ')'
        elif self.root == 2:
            return 'Variable Collection (Type: ' + str(self.root) + ')'

    def __repr__(self):
        if self.root is None:
            return repr(self[1]) + repr(self[2])
        else:
            out = str(self) + '\n'
            for child in self.children:
                out += '  ' + child[1] + ': Variable(' + str(child[2]) + ')\n'
            return out

    def parse(self, xmls):
        try:
            xmldocs = [minidom.parseString(xml) for xml in xmls]
        except:
            self.parent.log.error('ISY Could not parse variables, '
                                  + 'poorly formatted XML.')
        else:
            # parse definitions
            for ind in range(2):
                features = xmldocs[ind].getElementsByTagName('e')
                for feature in features:
                    self.vids.append(int(feature.attributes['id'].value))
                    self.vnames.append(feature.attributes['name'].value)
                    self.vtypes.append(ind + 1)

            # parse values
            count = 0
            for ind in range(2, 4):
                features = xmldocs[ind].getElementsByTagName('var')
                for feature in features:
                    init = feature.getElementsByTagName('init')[0] \
                        .firstChild.toxml()
                    val = feature.getElementsByTagName('val')[0] \
                        .firstChild.toxml()
                    ts_raw = feature.getElementsByTagName('ts')[0] \
                        .firstChild.toxml()
                    ts = datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S')
                    self.vobjs.append(Variable(self, self.vids[count], ind - 1,
                                               init, val, ts))
                    count += 1

            self.parent.log.info('ISY Loaded Variables')

    def update(self, waitTime=0):
        sleep(waitTime)
        xml = self.parent.conn.updateVariables()

        if xml is not None:
            try:
                xmldoc = minidom.parseString(xml)

                features = xmldoc.getElementsByTagName('var')
                for feature in features:
                    vid = int(feature.attributes['id'].value)
                    vtype = int(feature.attributes['type'].value)
                    init = feature.getElementsByTagName('init')[0] \
                        .firstChild.toxml()
                    val = feature.getElementsByTagName('val')[0] \
                        .firstChild.toxml()
                    ts_raw = feature.getElementsByTagName('ts')[0] \
                        .firstChild.toxml()
                    ts = datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S')

                    vobj = self[vtype][vid]
                    if vobj is None:
                        vobj = Variable(self, vid, vtype, init, val, ts)
                        self.vtypes.append(vtype)
                        self.vids.append(vid)
                        self.vnames.append('')
                        self.vobjs.append(vobj)
                    else:
                        vobj.init.update(init, force=True, silent=True)
                        vobj.val.update(val, force=True, silent=True)
                        vobj.lastEdit.update(ts, force=True, silent=True)

            except:
                self.parent.log.warning('ISY Failed to update variables, '
                                        + 'recieved bad XML.')

        else:
            self.parent.log.warning('ISY Failed to update variables.')

    def _upmsg(self, xml):
        xmldoc = minidom.parseString(xml)
        vtype = int(xmldoc.getElementsByTagName('var')[0]
                    .attributes['type'].value)
        vid = int(xmldoc.getElementsByTagName('var')[0]
                  .attributes['id'].value)
        vobj = self[vtype][vid]

        if '<init>' in xml:
            vobj.init.update(int(xmldoc.getElementsByTagName('init')[0]
                             .firstChild.toxml()), force=True)
        else:
            vobj.val.update(int(xmldoc.getElementsByTagName('val')[0]
                            .firstChild.toxml()), force=True)
            ts_raw = xmldoc.getElementsByTagName('ts')[0].firstChild.toxml()
            vobj.lastEdit.updat(datetime.strptime(ts_raw, '%Y%m%d %H:%M:%S'),
                                force=True)
        self.parent.log.debug('ISY Updated Variable: ' + str(vid))

    def __getitem__(self, val):
        if self.root is None:
            if val in [1, 2]:
                return Variables(self.parent, val, self.vids, self.vnames,
                                 self.vobjs, self.vtypes)
            else:
                raise AttributeError('Unknown variable type: ' + str(val))
        else:
            if type(val) is int:
                search_arr = self.vids
            else:
                search_arr = self.vnames

            notFound = True
            ind = -1
            while notFound:
                try:
                    ind = search_arr.index(val, ind + 1)
                    if self.vtypes[ind] == self.root:
                        notFound = False
                except ValueError:
                    break
            if notFound:
                raise AttributeError('Unrecognized variable id: ' + str(val))
            else:
                return self.vobjs[ind]

    def __setitem__(self, val):
        return None

    @property
    def children(self):
        if self.root is None:
            types = [1, 2]
        else:
            types = [self.root]

        out = []
        for ind in range(len(self.vids)):
            if self.vtypes[ind] in types:
                out.append((self.vtypes[ind], self.vnames[ind],
                            self.vids[ind]))
        return out
