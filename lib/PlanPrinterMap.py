#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - PlanPrinterMap.py

This is a replacement for PlanPrinter.py
With google maps support

original version by jpeterbaker
29 Sept 2014 - tvw V2.0 major updates
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from . import geometry
from matplotlib.patches import Polygon
import numpy as np
from . import agentOrder
import networkx as nx
from . import electricSpring
#from cStringIO import StringIO
from io import StringIO
from io import BytesIO
from PIL import Image
#import urllib2
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2
import math

# returns the points in a shrunken toward their centroid
def shrink(a):
    centroid = a.mean(1).reshape([2,1])
    return  centroid + .9*(a-centroid)

def commaGroup(n):
    # Returns a string of n with commas in place
    s = str(n)
    return ','.join([ s[max(i,0):i+3] for i in range(len(s)-3,-3,-3)][::-1])

class PlanPrinter:
    def __init__(self,a,outputDir,nagents,color='#FF004D',useGoogle=False,api_key=None):
        self.a = a
        self.n = a.order() # number of nodes
        self.m = a.size()  # number of links
                
        self.nagents = nagents
        self.outputDir = outputDir
        self.color = color

        # if the ith link to be made is (p,q) then orderedEdges[i] = (p,q)
        self.orderedEdges = [None]*self.m
        for e in a.edges_iter():
            self.orderedEdges[a.edge[e[0]][e[1]]['order']] = e

        # movements[i][j] is the index (in orderedEdges) of agent i's jth link
        self.movements = agentOrder.getAgentOrder(a,nagents,self.orderedEdges)

        # link2agent[i] is the agent that will make the ith link
        self.link2agent = [-1]*self.m
        for i in range(nagents):
            for e in self.movements[i]:
                self.link2agent[e] = i

        # keyneeds[i,j] = number of keys agent i needs for portal j
        self.agentkeyneeds = np.zeros([self.nagents,self.n],dtype=int)
        for i in range(self.nagents):
            for e in self.movements[i]:
                p,q = self.orderedEdges[e]
                self.agentkeyneeds[i][q] += 1

        self.names = np.array([a.node[i]['name'] for i in range(self.n)])
        # The alphabetical order
        self.nameOrder = np.argsort(self.names)

        self.xy = np.array([self.a.node[i]['xy'] for i in range(self.n)])

        # The order from north to south (for easy-to-find labels)
        self.posOrder = np.argsort(self.xy,axis=0)[::-1,1]

        # The inverse permutation of posOrder
        self.nslabel = [-1]*self.n
        for i in range(self.n):
            self.nslabel[self.posOrder[i]] = i

        self.maxNameLen = max([len(a.node[i]['name']) for  i in range(self.n)])

        # total stats for this plan
        self.num_portals = self.n
        self.num_links = self.m
        self.num_fields = -1

        if useGoogle:
            # convert xy coordinates to web mercator
            x_merc = np.array([128./np.pi * (self.a.node[i]['geo'][1] + np.pi) for i in self.a.node.keys()])
            min_x_merc = np.min(x_merc)
            #print "min_x_merc",min_x_merc
            x_merc = x_merc - min_x_merc
            #print "Xmin, Xmax",np.min(x_merc),np.max(x_merc)
            y_merc = np.array([128./np.pi * (np.pi - np.log(np.tan(np.pi/4. + self.a.node[i]['geo'][0]/2.))) for i in self.a.node.keys()])
            min_y_merc = np.min(y_merc)
            #print "min_y_merc",min_y_merc
            y_merc = y_merc - min_y_merc
            #print "Ymin, Ymax",np.min(y_merc),np.max(y_merc)
            # determine proper zoom such that the map is smaller than 640 on both sides
            zooms = np.arange(0,20,1)
            largest_x_zoom = 0
            largest_y_zoom = 0
            for zm in zooms:
                #print "X max",np.max(x_merc * 2.**zm + 20.)
                #print "Y max",np.max(y_merc * 2.**zm + 20.)
                if np.max(x_merc * 2.**zm) < 256.:
                    largest_x_zoom = zm
                    #print "X",largest_x_zoom
                if np.max(y_merc * 2.**zm) < 256.:
                    largest_y_zoom = zm
                    #print "Y",largest_y_zoom
            zoom = np.min([largest_x_zoom,largest_y_zoom])
            min_x_merc = min_x_merc*2.**(1+zoom)
            min_y_merc = min_y_merc*2.**(1+zoom)
            self.xy[:,0] = x_merc*2.**(1+zoom)
            self.xy[:,1] = y_merc*2.**(1+zoom)
            for i in range(self.n):
                self.a.node[i]['xy'] = self.xy[i]
            xsize = np.max(self.xy[:,0])+20
            ysize = np.max(self.xy[:,1])+20
            self.xylims = [-10,xsize-10,ysize-10,-10]
            # coordinates needed for google maps
            loncenter = np.rad2deg((min_x_merc+xsize/2.-10.)*np.pi/(128.*2.**(zoom+1)) - np.pi)
            latcenter = np.rad2deg(2.*np.arctan(np.exp(-1.*((min_y_merc+ysize/2.-10.)*np.pi/(128.*2.**(zoom+1)) - np.pi))) - np.pi/2.)
            #latmax = np.rad2deg(max([self.a.node[i]['geo'][0] for i in self.a.node.keys()]))
            #latmin = np.rad2deg(min([self.a.node[i]['geo'][0] for i in self.a.node.keys()]))
            #lonmax = np.rad2deg(max([self.a.node[i]['geo'][1] for i in self.a.node.keys()]))
            #lonmin = np.rad2deg(min([self.a.node[i]['geo'][1] for i in self.a.node.keys()]))
            #loncenter = (lonmax-lonmin)/2. + lonmin
            #latcenter = (latmax-latmin)/2. + latmin
            print ("Center Coordinates (lat,lon): ",latcenter,loncenter)

            # turn things in to integers for maps API
            map_xwidth = int(xsize)
            map_ywidth = int(ysize)
            zoom = int(zoom)+1

            # google maps API
            # get API key
            if api_key is not None:
                url = "http://maps.googleapis.com/maps/api/staticmap?center={0},{1}&size={2}x{3}&zoom={4}&sensor=false&key={5}".format(latcenter,loncenter,map_xwidth,map_ywidth,zoom,api_key)
            else:
                url = "http://maps.googleapis.com/maps/api/staticmap?center={0},{1}&size={2}x{3}&zoom={4}&sensor=false".format(latcenter,loncenter,map_xwidth,map_ywidth,zoom)
            #print url
        
            # determine if we can use google maps
            self.google_image = None
            try:
                buffer = BytesIO(urllib2.urlopen(url).read())
                self.google_image = Image.open(buffer)
                plt.clf()
            except urllib2.URLError as err:
                print("Could not connect to google maps server!")

    def keyPrep(self):
        rowFormat = '{0:11d} | {1:6d} | {2}\n'
        with open(self.outputDir+'keyPrep.txt','w') as fout:
            fout.write( 'Keys Needed | Lacked |\n')
            for i in self.nameOrder:
                keylack = max(self.a.in_degree(i)-self.a.node[i]['keys'],0)
                fout.write(rowFormat.format(\
                    self.a.in_degree(i),\
                    keylack,\
                    self.names[i]\
                ))

        unused   = set(range(self.n))
        infirst  = []
        outfirst = []

        for p,q in self.orderedEdges:
            if p in unused:
                outfirst.append(self.names[p])
                unused.remove(p)
            if q in unused:
                infirst.append(self.names[q])
                unused.remove(q)

        infirst.sort()
        outfirst.sort()

        with open(self.outputDir+'ownershipPrep.txt','w') as fout:
            fout.write("These portals' first links are incoming\n")
            fout.write('They should be at full resonators before linking\n')
            for s in infirst:
                fout.write('  %s\n'%s)

            fout.write("\nThese portals' first links are outgoing\n")
            fout.write('Their resonators can be applied when first agent arrives\n')
            for s in outfirst:
                fout.write('  %s\n'%s)


    def agentKeys(self):
        rowFormat = '%4s %4s %s\n'
        csv_file = open(self.outputDir+'keys_for_agents.csv','w')
        csv_file.write('agent, mapNum, name, keys\n')
        for agent in range(self.nagents):
            with open(self.outputDir+'keys_for_agent_%s_of_%s.txt'\
                    %(agent+1,self.nagents),'w') as fout:
                fout.write('Keys for Agent %s of %s\n\n'%(agent+1,self.nagents))
                fout.write('Map# Keys Name\n')

                for portal in self.nameOrder:
                    
                    keys = self.agentkeyneeds[agent,portal]
                    if self.agentkeyneeds[agent,portal] == 0:
                        keys = ''
                        
                    fout.write(rowFormat%(\
                        self.nslabel[portal],\
                        keys,\
                        self.names[portal]\
                    ))
                    csv_file.write('{0}, {1}, {2}, {3}\n'.\
                                   format(agent,self.nslabel[portal],
                                          self.names[portal],keys))
        csv_file.close()

    def drawBlankMap(self):
        plt.plot(self.xy[:,0],self.xy[:,1],'o',ms=16,color=self.color)

        for i in range(self.n):
            plt.text(self.xy[i,0],self.xy[i,1],self.nslabel[i],\
                     fontweight='bold',ha='center',va='center',fontsize=10)

    def drawSubgraph(self,edges=None):
        '''
        Draw a subgraph of a
        Only includes the edges in 'edges'
        Default is all edges
        '''
        if edges == None:
            edges = range(self.m)

#        anchors = np.array([ self.xy[self.orderedEdges[e],:] for e in edges]).mean(1)
#        edgeLabelPos = electricSpring.edgeLabelPos(self.xy,anchors)
#
#        self.drawBlankMap()
#
#        for i in range(len(edges)):
#            j = edges[i]
#            p,q = self.orderedEdges[j]
#            plt.plot([ self.xy[p,0],edgeLabelPos[i,0],self.xy[q,0] ]  ,\
#                     [ self.xy[p,1],edgeLabelPos[i,1],self.xy[q,1] ],'r-')
#
#            plt.text(edgeLabelPos[i,0],edgeLabelPos[i,1],j,\
#                     ha='center',va='center')

### The code below works. It just uses networkx draw functions
        if edges == None:
            b = self.a
        else:
            b = nx.DiGraph()
            b.add_nodes_from(range(self.n))

            b = nx.DiGraph()
            b.add_nodes_from(range(self.n))

            for e in edges:
                p,q = self.orderedEdges[e]
                b.add_edge(p,q,{'order':e})

        edgelabels = dict([ (e,self.a.edge[e[0]][e[1]]['order'])\
                            for e in b.edges_iter() ])

        plt.plot(self.xy[:,0],self.xy[:,1],'o',ms=16,color=self.color)

        for j in range(self.n):
            i = self.posOrder[j]
            plt.text(self.xy[i,0],self.xy[i,1],j,\
                     fontweight='bold',ha='center',va='center')

        try:
            nx.draw_networkx_edge_labels(b,self.ptmap,edgelabels,font_size=8,
                                         bbox=dict(boxstyle="round",fc="w"))
        except AttributeError:
            self.ptmap   = dict([(i,self.a.node[i]['xy']) for i in range(self.n) ])
            nx.draw_networkx_edge_labels(b,self.ptmap,edgelabels,font_size=8,
                                         bbox=dict(boxstyle="round",fc="w"))

        # edge_color does not seem to support arbitrary colors easily
        if self.color == '#3BF256':
            nx.draw_networkx_edges(b,self.ptmap,edge_color='g')
        elif self.color == '#2ABBFF':
            nx.draw_networkx_edges(b,self.ptmap,edge_color='k')
        else:
            nx.draw_networkx_edges(b,self.ptmap,edge_color='k')
        plt.axis('off')

    def planMap(self,useGoogle=False):
        fig = plt.figure()
        ax  = fig.add_subplot(111)
        if useGoogle:
            if self.google_image is None:
                return
            implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
        # Plot labels aligned to avoid other portals
        for j in range(self.n):
            i = self.posOrder[j]
            plt.plot(self.xy[i,0],self.xy[i,1],'o',color=self.color)

            displaces = self.xy[i] - self.xy
            displaces[i,:] = np.inf

            nearest = np.argmin(np.abs(displaces).sum(1))

            if self.xy[nearest,0] < self.xy[i,0]:
                ha = 'left'
            else:
                ha = 'right'
            if self.xy[nearest,1] < self.xy[i,1]:
                va = 'bottom'
            else:
                va = 'top'
            
            plt.text(self.xy[i,0],self.xy[i,1],str(j),ha=ha,va=va)

        fig = plt.gcf()
        #fig.set_size_inches(8.5,11)
        if useGoogle: plt.axis(self.xylims)
        plt.axis('off')
        plt.title('Portals numbered north to south\nNames on key list')
        plt.savefig(self.outputDir+"portalMap.png")
        plt.clf()

        if useGoogle:
            if self.google_image is None:
                return
            implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
        # Draw the map with all edges in place and labeled
        self.drawSubgraph()
        if useGoogle: plt.axis(self.xylims)
        plt.axis('off')
        plt.title('Portal and Link Map')
        plt.savefig(self.outputDir+"linkMap.png")
        plt.clf()

#        for agent in range(self.nagents):
#            self.drawSubgraph(self.movements[agent])
#            plt.axis(xylims)
#            plt.savefig(self.outputDir+'linkMap_agent_%s_of_%s.png'%(agent+1,self.nagents))
#            plt.clf()

    def agentLinks(self):
        # Total distance traveled by each agent
        agentdists = np.zeros(self.nagents)
        # Total experience for each agent
        agentexps  = np.zeros(self.nagents,dtype=int)

        for i in range(self.nagents):
            movie = self.movements[i]
            # first portal in first link
            curpos = self.a.node[self.orderedEdges[movie[0]][0]]['geo']
            for e in movie[1:]:
                p,q = self.orderedEdges[e]
                newpos = self.a.node[p]['geo']
                dist = geometry.sphereDist(curpos,newpos)
                agentdists[i] += dist
                curpos = newpos

                agentexps[i] += 313 + 1250*len(self.a.edge[p][q]['fields'])

        # Different formatting for the agent's own links
        plainStr = '{0:4d}{1:1s} {2: 5d}{3:5d} {4:s}\n            {5:4d} {6:s}\n\n'
        hilitStr = '{0:4d}{1:1s} {2:_>5d}{3:5d} {4:s}\n            {5:4d} {6:s}\n\n'

        csv_file = open(self.outputDir+'links_for_agents.csv','w')
        
        for agent in range(self.nagents):
            with open(self.outputDir+'links_for_agent_%s_of_%s.txt'\
                    %(agent+1,self.nagents),'w') as fout:

                fout.write('Complete link schedule issued to agent %s of %s\n'\
                    %(agent+1,self.nagents))
                
                totalTime = self.a.walktime+self.a.linktime+self.a.commtime

                fout.write('\nTotal time estimate: %s minutes\n\n'%int(totalTime/60+.5))

                fout.write('Agent distance:   %s m\n'%int(agentdists[agent]))
                fout.write('Agent experience: %s AP\n'%(agentexps[agent]))

                fout.write('\nLinks marked with * can be made EARLY\n')

                fout.write('\nLink  Agent Map# Link Origin\n')
                fout.write('                 Link Destination\n')
                fout.write('-----------------------------------\n')
                #             1234112345612345 name
                csv_file.write('Link, Agent, MapNumOrigin, OriginName, MapNumDestination, DestinationName\n')
                
                for i in range(self.m):
                    p,q = self.orderedEdges[i]
                    
                    linkagent = self.link2agent[i]

                    # Put a star by links that can be completed early since they complete no fields
                    numfields = len(self.a.edge[p][q]['fields'])
                    if numfields == 0:
                        star = '*'
#                        print '%s %s completes nothing'%(p,q)
                    else:
                        star = ''
#                        print '%s %s completes'%(p,q)
#                        for t in self.a.edge[p][q]['fields']:
#                            print '   ',t

                    if linkagent != agent:
                        fout.write(plainStr.format(\
                            i,\
                            star,\
                            linkagent+1,\
                            self.nslabel[p],\
                            self.names[p],\
                            self.nslabel[q],\
                            self.names[q]\
                        ))
                    else:
                        fout.write(hilitStr.format(\
                            i,\
                            star,\
                            linkagent+1,\
                            self.nslabel[p],\
                            self.names[p],\
                            self.nslabel[q],\
                            self.names[q]\
                        ))
                    csv_file.write("{0}{1}, {2}, {3}, {4}, {5}, {6}\n".\
                                   format(i,star,linkagent+1,
                                          self.nslabel[p],self.names[p],
                                          self.nslabel[q],self.names[q]))
        csv_file.close()

    def animate(self,useGoogle=False):
        """
        Show how the links will unfold
        """
        fig = plt.figure()
        ax  = fig.add_subplot(111)

        GREEN     = ( 0.0 , 1.0 , 0.0 , 0.3)
        BLUE      = ( 0.0 , 0.0 , 1.0 , 0.3)
        RED       = ( 1.0 , 0.0 , 0.0 , 0.5)
        INVISIBLE = ( 0.0 , 0.0 , 0.0 , 0.0 )

        portals = np.array([self.a.node[i]['xy']
                            for i in self.a.nodes_iter()]).T
        
        # Plot all edges lightly
        def dashAllEdges():
            for p,q in self.a.edges_iter():
                plt.plot(portals[0,[p,q]],portals[1,[p,q]],'k:')

        aptotal = 0
        edges   = []
        patches = []

        if useGoogle:
            if self.google_image is None:
                return
            implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
        plt.plot(portals[0],portals[1],marker='o',markerfacecolor='#2ABBFF',linestyle=' ')
        dashAllEdges()

        plt.title('AP:\n%s'%commaGroup(aptotal),ha='center')
        if useGoogle: plt.axis(self.xylims)
        plt.axis('off')
        plt.savefig(self.outputDir+'frame_-1.png')
        plt.clf()

        # let's plot some stuff
        for i in range(self.m):
            if useGoogle:
                if self.google_image is None:
                    return
                implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
            p,q = self.orderedEdges[i]
            plt.plot(portals[0],portals[1],marker='o',markerfacecolor='#2ABBFF', linestyle=' ')
            # Plot all edges lightly
            dashAllEdges()
            for edge in edges:
                plt.plot(edge[0],edge[1],color='#2ABBFF')

            # We'll display the new fields in red
            newPatches = []
            for tri in self.a.edge[p][q]['fields']:
                coords = np.array([ self.a.node[v]['xy'] for v in tri ])
                newPatches.append(Polygon(shrink(coords.T).T,facecolor=RED,\
                                                 edgecolor=INVISIBLE))
            
            aptotal += 313+1250*len(newPatches)
            newEdge = np.array([self.a.node[p]['xy'],self.a.node[q]['xy']]).T
            patches += newPatches
            edges.append(newEdge)            
            plt.plot(newEdge[0],newEdge[1],'k-',lw=2)
            x0 = newEdge[0][0]
            x1 = newEdge[0][1]
            y0 = newEdge[1][0]
            y1 = newEdge[1][1]
            plt.plot([x1-0.05*(x1-x0),x1-0.4*(x1-x0)],
                     [y1-0.05*(y1-y0),y1-0.4*(y1-y0)],'k-',lw=6)
            ax = plt.gca()
            for patch in patches:
                ax.add_patch(patch)
            ax.set_title('AP:\n%s'%commaGroup(aptotal),ha='center')
            if useGoogle: plt.axis(self.xylims)
            ax.axis('off')
            plt.savefig(self.outputDir+'frame_{0:03d}.png'.format(i))
            ax.cla()
                
            # reset patches to green
            for patch in newPatches:
                patch.set_facecolor("#2ABBFF")

        if useGoogle:
            if self.google_image is None:
                return
            implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')

        plt.plot(portals[0],portals[1],marker='o',markerfacecolor='#2ABBFF')
        for edge in edges:
            plt.plot(edge[0],edge[1],color='#2ABBFF',linestyle='-')
        for patch in patches:
            ax.add_patch(patch)
        ax.set_title('AP:\n%s'%commaGroup(aptotal),ha='center')
        if useGoogle: plt.axis(self.xylims)
        ax.axis('off')
        plt.savefig(self.outputDir+'frame_{0:03d}.png'.format(self.m))
        ax.cla()

        self.num_fields = len(patches)

    def split3instruct(self, useGoogle=False):
        portals = np.array([self.a.node[i]['xy'] for i in self.a.nodes_iter()]).T
        
        gen1 = self.a.triangulation

        oldedges = []

        plt.clf()
        if useGoogle:
            if self.google_image is None:
                return
            implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
        plt.plot(portals[0],portals[1],marker='o',markerfacecolor='#2ABBFF',linestyle=' ')
        # plt.plot(portals[0],portals[1],'go')
        if useGoogle: plt.axis(self.xylims)
        plt.axis('off')
        plt.savefig(self.outputDir+'depth_-1.png')
        plt.clf()

        depth = 0
        while True:
            # newedges[i][0] has the x-coordinates of both verts of edge i
            newedges = [ np.array([
                                self.a.node[p]['xy'] ,\
                                self.a.node[q]['xy']
                         ]).T\
                             for j in range(len(gen1)) \
                             for p,q in gen1[j].edgesByDepth(depth)\
                       ]

            if len(newedges) == 0:
                break

            if useGoogle:
                if self.google_image is None:
                    return
                implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
            plt.plot(portals[0],portals[1],marker='o',markerfacecolor='#2ABBFF', linestyle='-')

            for edge in oldedges:
                plt.plot(edge[0],edge[1],'k-')

            for edge in newedges:
                plt.plot(edge[0],edge[1],'r-')
            
            oldedges += newedges
            if useGoogle: plt.axis(self.xylims)
            plt.axis('off')
            plt.savefig(self.outputDir+'depth_{0:03d}.png'.format(depth))
            plt.clf()

            depth += 1

        if useGoogle:
            if self.google_image is None:
                return
            implot = plt.imshow(self.google_image,extent=self.xylims,origin='upper')
        plt.plot(portals[0],portals[1],marker='o',markerfacecolor='#2ABBFF',linestyle='-')

        for edge in oldedges:
            plt.plot(edge[0],edge[1],'k-')
        if useGoogle: plt.axis(self.xylims)
        plt.axis('off')
        plt.savefig(self.outputDir+'depth_{0:03d}.png'.format(depth))
        plt.clf()
