#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - maxfield.py

General code to optimize fielding strategy.

Original version by jpeterbaker
29 Sept 2014 - tvw V2.0 major updates
"""
from . import geometry
np = geometry.np
from .Triangle import Triangle,Deadend

'''
Some things are chosen randomly:
    Each triangle's splitting portal
    Each triangle's "final node" (unless determined by parent)
This is the number of times to randomly rebuild each first generation triangle while attempting to get it right
'''
TRIES_PER_TRI = 10

def canFlip(degrees,keylacks,p,q):
    '''
    True iff reversing edge p,q is a paraeto improvement
        out-degree of q must be <8
        p must have a key surplus
    '''
    return (degrees[q,1] < 8) & (keylacks[p]<0)

def flip(a,p,q,degrees=None,keylacks=None):
    if not a.edge[p][q]['reversible']:
        print ('!!!! Trying to reverse a non-reversible edge !!!!')
        print (p,q)
    # Give the reversed edge the same properties
    a.add_edge(q,p,a.edge[p][q])
    a.remove_edge(p,q)
    if degrees is not None:
        degrees[p,0] += 1
        degrees[p,1] -= 1
        degrees[q,0] -= 1
        degrees[q,1] += 1

    if keylacks is not None:
        keylacks[p] += 1
        keylacks[q] -= 1

def flipSome(a):
    '''
    Tries to make each in and out degree of a <=8 by reversing edges
    Only edges with the property reversible=True will be flipped
    '''
    n = a.order()
    degrees  = np.empty([n,2],dtype=int)
    keylacks = np.empty(n,dtype=int) # negative if there's a surplus

    # column 0 is in-degree, col 1 is out-degree
    for i in range(n):
        degrees[i,0] = a.in_degree(i)
        degrees[i,1] = a.out_degree(i)
        keylacks[i] = degrees[i,0]-a.node[i]['keys']

    # We can never make more than 8 outogoing links. Reducing these is first priority
    manyout = (degrees[:,1]>8).nonzero()[0]
    for p in manyout:
        print ("Found a portal with more than 8 outgoing links: %s"%p)
        qs = list(a.edge[p].iterkeys())
        for q in qs:
            if a.edge[p][q]['reversible'] and canFlip(degrees,keylacks,p,q):
                flip(a,p,q,degrees,keylacks)
            if degrees[p,1] <= 8:
                break
        else:
            # This runs if the for loop exits without the break
            print ('Could not reduce OUT-degree sufficiently for %s'%p)

    # It is difficult to gather more keys. Reducing key-gathering is next priority
    # We'll process the ones with the greatest need first
    needkeys = (keylacks>0).nonzero()[0]
    needkeys = needkeys[np.argsort(keylacks[needkeys])][::-1]
    for q in needkeys:
        for p,q2 in a.in_edges(q):
            if a.edge[p][q]['reversible'] and canFlip(degrees,keylacks,p,q):
                flip(a,p,q,degrees,keylacks)
            if keylacks[q] <= 0:
                break
#        else:
            # This runs if the for loop exits without the break
#            print 'Could not reduce IN-degree sufficiently for %s'%q


def removeSince(a,m,t):
    # Remove all but the first m edges from a (and .edge_stck)
    # Remove all but the first t Triangules from a.triangulation
    for i in range(len(a.edgeStack) - m):
        p,q = a.edgeStack.pop()
        a.remove_edge(p,q)
#        print 'removing',p,q
#        print a.edgeStack
    while len(a.triangulation) > t:
        a.triangulation.pop()


def triangulate(a,perim):
    '''
    Recursively tries every triangulation in search a feasible one
        Each layer
            makes a Triangle out of three perimeter portals
            for every feasible way of max-fielding that Triangle
                try triangulating the two perimeter-polygons to the sides of the Triangle

    Returns True if a feasible triangulation has been made in graph a
    '''
    pn = len(perim)
    if pn < 3:
        return True

    try:
        startStackLen = len(a.edgeStack)
    except AttributeError:
        startStackLen = 0
        a.edgeStack = []
    try:
        startTriLen = len(a.triangulation)
    except AttributeError:
        startTriLen = 0
        a.triangulation = []

    # Try all triangles using perim[0:2] and another perim node
    for i in np.random.permutation(range(2,pn)):

        for j in range(TRIES_PER_TRI):
            t0 = Triangle(perim[[0,1,i]],a,True)
            t0.findContents()
            t0.randSplit()
            try:
                t0.buildGraph()
            except Deadend as d:
                # remove the links formed since beginning of loop
                removeSince(a,startStackLen,startTriLen)
            else:
                # This build was successful. Break from the loop
                break
        else:
            # The loop ended "normally" so this triangle failed
            continue

        if not triangulate(a,perim[range(1,i   +1   )]): # 1 through i
            # remove the links formed since beginning of loop
            removeSince(a,startStackLen,startTriLen)
            continue

        if not triangulate(a,perim[range(0,i-pn-1,-1)]): # i through 0
           # remove the links formed since beginning of loop
           removeSince(a,startStackLen,startTriLen)
           continue

        # This will be a list of the first generation triangles
        a.triangulation.append(t0)

        # This triangle and the ones to its sides succeeded
        return True

    # Could not find a solution
    return False
    
def maxFields(a):
    n = a.order()

    pts = np.array([ a.node[i]['xy'] for i in range(n) ])

    perim = np.array(geometry.getPerim(pts))
    if not triangulate(a,perim):
        return False
    flipSome(a)

    return True

