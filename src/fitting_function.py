'''
Construction of the fitting functions (for each tooth, for each landmark)
by sampling along the profile normal to the boundary in the training set
and building a statistical model of the grey-level structure.
@author     Matthias Moulin & Milan Samyn
@version    1.0
'''

import cv2
import numpy as np
import scipy.spatial.distance as dist
import configuration as c
import math
import math_utils as mu

def create_fitting_functions(GS):
    '''
    Creates the fitting function for each tooth, for each landmark.
    @param GS:              the matrix GS which contains for each tooth, for each of the given training samples,
                            for each landmark, a normalized sample (along the profile normal through that landmark)
    @return The fitting function for each tooth, for each landmark.
    '''          
    fs = [[get_fitting_function(tooth, landmark, GS) for landmark in range(c.get_nb_landmarks())] for tooth in range(c.get_nb_teeth())]        
    return fs  
    
def get_fitting_function(tooth_index, landmark_index, GS):
    '''
    Creates the fitting function for the given tooth index, for the given landmark index.
    @param tooth_index:     the index of the tooth (in GS)
    @param landmark_index:  the index of the landmark (in GS)
    @param GS:              the matrix GS which contains for each tooth, for each of the given training samples,
                            for each landmark, a normalized sample (along the profile normal through that landmark)
    @return The fitting function for the given tooth index, for the given landmark index.
    '''
    G = np.zeros((GS.shape[1], GS.shape[3]))
    #Iterate all the training samples
    for i in range(GS.shape[1]):
        G[i,:] = GS[tooth_index, i, landmark_index, :]
    
    G -= G.mean(axis=0)[None, :]
    C = (np.dot(G.T, G) / float(G.shape[0])) #Covariance matrix
    g_mu = G.mean(axis=0) #Model mean
    
    def fitting_function(gs):
        '''
        Calculate the Mahalanobis distance for the given sample.
        @param: gs           the new sample
        @return The Mahalanobis distance for the given sample.
        '''
        #Use the Moore-Penrose pseudo-inverse because C can be singular
        return dist.mahalanobis(gs, g_mu, np.linalg.pinv(C))

    return fitting_function  
    
def create_partial_GS(trainingSamples, XS, MS, offsetX=0, offsetY=0, k=5, method=''):
    '''
    Creates the matrix GS which contains for each tooth, for each of the given training samples,
    for each landmark, a normalized sample (along the profile normal through that landmark).
    @param trainingSamples: the number of the training samples (not the test training samples!)
    @param XS:              contains for each tooth, for each training sample, all landmarks (in the image coordinate frame)
    @param MS:              contains for each tooth, the tooth model (in the model coordinate frame)
    @param offsetX:         the possible offset in x direction (used when working with cropped images and non-cropped landmarks)
    @param offsetY:         the possible offset in y direction (used when working with cropped images and non-cropped landmarks)
    @param k:               the number of pixels to sample either side for each of the model points along the profile normal
    @param method:          the method used for preprocessing
    @return The matrix GS which contains for each tooth, for each of the given training samples,
            for each landmark, a normalized sample (along the profile normal through that landmark).
    '''
    GS = np.zeros((c.get_nb_teeth(), len(trainingSamples), c.get_nb_landmarks(), 2*k+1))
    for j in range(c.get_nb_teeth()):
        index = 0
        for i in trainingSamples:
            # model of tooth j from model coordinate frame to image coordinate frame
            xs, ys = mu.extract_coordinates(mu.full_align_with(MS[j], XS[j,index,:]))
            fname = c.get_fname_vis_pre(i, method)
            img = cv2.imread(fname)
            GS[j,index,:] = create_G(img, k, xs, ys, offsetX, offsetY)
            index += 1
    return GS
                 
def create_G(img, k, xs, ys, offsetX=0, offsetY=0):
    '''
    Sample along the profile normal k pixels either side for each of the given model
    points (xs[i], ys[i]) in the given image to create the matrix G, which contains
    for each landmark a normalized sample.
    @param img:          the image
    @param k:            the number of pixels to sample either side for each of the
                         given model points (xs[i], ys[i]) along the profile normal
    @param i:            the index of the model point
    @param xs:           x positions of the model points in the image
    @param ys:           y positions of the model points in the image
    @param offsetX:      the possible offset in x direction (used when working with cropped images and non-cropped xs & ys)
    @param offsetY:      the possible offset in y direction (used when working with cropped images and non-cropped xs & ys)
    @return The matrix G, which contains for each landmark a normalized sample.
    '''
    G = np.zeros((c.get_nb_landmarks(), 2*k+1))
    for i in range(c.get_nb_landmarks()): #For all model points of a certain tooth model
        Gi, Coords = create_Gi(img, k, i, xs, ys, offsetX, offsetY)
        G[i,:] = normalize_Gi(Gi)
    return G
    
def normalize_Gi(Gi):
    '''
    Normalizes the given sample Gi by dividing through by the sum of the
    absolute element values.
    @param Gi:           the sample to normalize
    @return The normalized sample.
    '''
    norm = 0
    for j in range(Gi.shape[0]):
        norm += abs(Gi[j])
    if norm==0: 
        return Gi
    return Gi/norm
    
def create_Gi(img, k, i, xs, ys, offsetX=0, offsetY=0, sx=1, sy=1):
    '''
    Sample along the profile normal k pixels either side of the given model point (xs[i], ys[i])
    in the given image to create a (non-normalized) vector Gi.
    @param img:          the image
    @param k:            the number of pixels to sample either side of the given model
                         point (xs[i], ys[i]) along the profile normal
    @param i:            the index of the model point
    @param xs:           x positions of the model points in the image
    @param ys:           y positions of the model points in the image
    @param offsetX:      the possible offset in x direction (used when working with cropped images and non-cropped xs & ys)
    @param offsetY:      the possible offset in y direction (used when working with cropped images and non-cropped xs & ys)
    @param sx:           the step to multiply the profile normal x-change in direction with
    @param sy:           the step to multiply the profile normal y-change in direction with
    @return The (non-normalized) vector Gi and a vector containing the coordinates
            of all the sample points used. (First the most distant point when adding
            a positive change, last the most distant point when adding a negative change) 
    '''
    x = xs[i] - offsetX
    y = ys[i] - offsetY
    if (i == 0):
        x_min = xs[-1] - offsetX
        y_min = ys[-1] - offsetY
        x_max = xs[1] - offsetX
        y_max = ys[1] - offsetY
    elif (i == xs.shape[0]-1):
        x_min = xs[(i-1)] - offsetX
        y_min = ys[(i-1)] - offsetY
        x_max = xs[0] - offsetX
        y_max = ys[0] - offsetY
    else:
        x_min = xs[(i-1)] - offsetX
        y_min = ys[(i-1)] - offsetY
        x_max = xs[(i+1)] - offsetX
        y_max = ys[(i+1)] - offsetY
        
    dx = x_max - x_min
    dy = y_max - y_min
    sq = math.sqrt(dx*dx+dy*dy)
    
    #Profile Normal to Boundary
    nx = (- dy / sq) * sx
    ny = (dx / sq) * sy
    
    #We explicitly don't want a normalized vector at this stage
    return create_raw_Gi(img, k, x, y, nx, ny)
    
        
def create_raw_Gi(img, k, x, y, nx, ny):
    '''
    Sample along the profile normal characterized by (nx, ny) k pixels either side
    of the given model point (x, y) in the given image to create a (non-normalized) vector Gi.
    @param img:          the image
    @param k:            the number of pixels to sample either side of the given model
                         point along the profile normal characterized by (nx, ny)
    @param x:            x position of the model point in the image
    @param y:            y position of the model point in the image
    @param nx:           profile normal x-change in direction (step/magnitude included)
    @param ny:           profile normal y-change in direction (step/magnitude included)
    @return The (non-normalized) vector Gi and a vector containing the coordinates
            of all the sample points used. (First the most distant point when adding
            a positive change, last the most distant point when adding a negative change) 
    '''
    Gi = np.zeros((2*k+2))
    Coords = np.zeros(2*(2*k+2))
    
    index = 0
    for i in range(k+1,0,-1): #Downwards the normal
        kx = int(x - i * nx)
        ky = int(y - i * ny)
        Gi[index] = img[ky,kx,0]
        Coords[(2*index)] = kx
        Coords[(2*index+1)] = ky
        index += 1
        
    Gi[index] = img[y,x,0] #The model point itself
    Coords[(2*index)] = x
    Coords[(2*index+1)] = y
    index += 1
        
    for i in range(1,k+1): #Upwards the normal
        kx = int(x + i * nx)
        ky = int(y + i * ny)
        Gi[index] = img[ky,kx,0]
        Coords[(2*index)] = kx
        Coords[(2*index+1)] = ky
        index += 1
       
    Gi = (Gi[1:] - Gi[:-1]) #All but the first sample minus all but the last sample
    
    #We explicitly don't want a normalized vector at this stage
    return Gi, Coords[2:]
