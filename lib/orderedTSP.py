#!/usr/bin/env python
# -*- coding: utf-8 -*-

from . import branch_bound
np = branch_bound.np

MAX_BRANCHES = 10000

# This could be used if more splits are wanted than are possible
infState = branch_bound.InfState()

class OTSPstate:
    def __init__(self,d,order,nagents,visit2agent=[0],time=[0.],lastat=None,):
        '''
        d: distance matrix
        order: order in which nodes must be visited
        time: time at which the nodes were visited
        lastat[i,j]: the node where agent j most recently was at time[i]
        nagents: number of agents
        visit2agent[i] is the agent who makes visit i
        '''
        # This is the root
        if lastat == None:
            self.n = d.shape[0]

            lastat = [[None]*nagents]
            lastat[0][0] = 0

            # Make a "start location" that is at distance 0 from everywhere
            # Using index -1 for undeployed agents puts them at this "start"
        else:
            # "start" location has already been added but doesn't count
            self.n = d.shape[0] - 1

        self.d = d

        self.lastat = lastat

        self.order = order
        self.nagents = nagents
        self.visit2agent = visit2agent
        self.time = time
        self.m = len(time) # numer of visits that have already been made

        self.value = self.time[-1]

    def agentsNewTime(self,agent):
        # The time at which this agent could make the next visit
        
        # The index of the last visit this agent made
        lastvisit = self.lastat[-1][agent]

#        print len(self.time)
#        print self.d.shape
#        print 'agent',agent
#        print '  lastvisit',lastvisit

        # Assume agent's initial deployment is instantaneous
        if lastvisit == None:
            return self.time[-1]

        # The node at which agent made his last visit
        lastpos   = self.order[lastvisit]
        # The time at which agent was at lastpos
        lasttime  = self.time[lastvisit]
        # The node that needs to be visited next
        nextpos = self.order[self.m]

#        print '  lastat',self.lastat
#        print '  lastpos',lastpos
#        print '  lasttime',lasttime
#        print '  nextpos',nextpos

        t = max( self.time[-1] , lasttime + self.d[nextpos,lastpos] )
#        print '  t',t
        return t

        # He makes it either at the same time as the previous visit or as soon as he arrives at nextpos
        return max( self.time[-1] , lasttime + self.d[nextpos,lastpos] )

    def split(self,num):
        '''
        num: number of child states to produce
            (in the easiest case, this is the same as nagents)

        produces self.children states
        '''
        if self.m >= len(self.order):
            raise branch_bound.CantSplit()

        self.children = []
        for agent in range(self.nagents):
            newtime = self.agentsNewTime(agent)
            
            # Everyone's last known position is the same, except that agent is now at m
            newlast = list(self.lastat[-1])
            newlast[agent] = self.m

            self.children.append(OTSPstate(self.d,self.order,self.nagents,\
                                 self.visit2agent+[agent],\
                                 self.time+[newtime],\
                                 self.lastat+[newlast],\
                                ))
        if num < self.nagents:
            childorder = np.argsort([ child.value for child in self.children ])
            self.children = np.array(self.children)
            self.children = self.children[childorder[:num]]

    def calcTimes(self):
        '''
        Calculates self.time and self.lastat
            Uses data from self.d and self.visit2agent
        Assumes self.time[0] should be 0
        self.time and self.lastat are overwritten
        '''
        nvisits = len(self.order)

        # These could be pre-allocated if agentsNewTime didn't use negativ index

        # Same initialization as in __init__
        self.time        = [0.]
        self.m           = 1
        # Agent 0 makes visit 0
        self.lastat = [ [0]+[None]*(self.nagents-1) ]

        for i in xrange(1,nvisits):
            agent = self.visit2agent[i]

            t = self.agentsNewTime(agent)

            self.time.append(t)
            self.m += 1

            # Everyone has same position except for agent
            self.lastat.append(list(self.lastat[-1]))
            self.lastat[-1][agent] = i
            
        self.children = []
        self.value = self.time[-1]
        return self.value


def getVisits(dists,order,nagents):
    '''
    dists:   a distance matrix
    order:   the order in which nodes must be visited
             duplicates allowed
    nagents: the number of agents available to make the visits
             
    returns visits,time
              visits[i] = j means the ith visit should be performed by agent j
              time[i] is the number of meters a person could have walked walk since the start when visit i is made 
    '''
    root = OTSPstate(dists,order,nagents)
    LO = MAX_BRANCHES // nagents
    state,value = branch_bound.branch_bound(root, LO , LO*nagents)

    return state.visit2agent,state.time

if __name__=='__main__':
    import geometry
#    pts = np.array([[0,0],\
#                    [0,1],\
#                    [0,5]])
#    order = [0,2,1]
#    pts = np.array([[0,0],\
#                    [0,1],\
#                    [0,2],\
#                    [0,3],\
#                    [0,5]])
#    order = [0,4,1,2,3]
    pts = np.array([[0,0],\
                    [3,0],\
                    [4,0],\
                    [7,0]])
    order       = [0,2,1,3]
    visit2agent = [0,0,0,0]

    d = geometry.planeDist(pts,pts)

#    print getVisits(d,order,2)

    state = OTSPstate(d,order,2,visit2agent)
    print (state.calcTimes())

