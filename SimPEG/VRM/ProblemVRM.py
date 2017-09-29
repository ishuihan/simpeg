from SimPEG import Problem
from SimPEG.VRM.SurveyVRM import SurveyVRM
# from SimPEG.VRM.FieldsVRM import Fields_LinearFWD
import numpy as np
import scipy.sparse as sp
import discretize # <-- only for temporary gridH function







############################################
# BASE VRM PROBLEM CLASS
############################################

class BaseProblemVRM(Problem.BaseProblem):

	def __init__(self, mesh, **kwargs):

		assert len(mesh.h) == 3, 'Problem requires 3D tensor or OcTree mesh'

		refFact = 3
		refRadius = 1.25*np.mean(np.r_[np.min(mesh.h[0]),np.min(mesh.h[1]),np.min(mesh.h[2])])*np.r_[1.,2.,3.]

		assert len(refRadius) == refFact, 'Number of refinement radii must equal refinement factor'

		super(BaseProblemVRM,self).__init__(mesh, **kwargs)


		self.surveyPair = SurveyVRM
		self.refFact = refFact
		self.refRadius = refRadius
		self.A = None
		self.Tb = None
		self.Tdbdt = None

	# LOCAL FUNCTION FOR GETTING CELL WIDTHS
	def fcngridH(self,meshObj):

		if isinstance(meshObj, discretize.TreeMesh):
			H = np.zeros((len(meshObj._cells),meshObj.dim))
			for ii, ind in enumerate(meshObj._sortedCells):
			    p = meshObj._asPointer(ind)
			    H[ii, :] = meshObj._cellH(p)
			return H
		elif isinstance(meshObj, discretize.TensorMesh):
			H = meshObj.h
			H = np.meshgrid(H[0],H[1],H[2])
	        hx = np.reshape(H[0],meshObj.nC)
	        hy = np.reshape(H[1],meshObj.nC)
	        hz = np.reshape(H[2],meshObj.nC)
	        return np.c_[hx,hy,hz]

	def getH0matrix(self, xyz, pp):

		# Creates sparse matrix containing inducing field components for source pp
		# 
		# INPUTS
		# xyz: N X 3 array of locations to predict field
		# pp: Source index

		SrcObj = self.survey.srcList[pp]

		H0 = SrcObj.getH0(xyz)

		Hx0 = sp.diags(H0[:,0], format="csr")
		Hy0 = sp.diags(H0[:,1], format="csr")
		Hz0 = sp.diags(H0[:,2], format="csr")

		H0 = sp.vstack([Hx0,Hy0,Hz0])

		return H0

	def getGeometryMatrix(self, xyzc, xyzh, pp):

		# Creates dense geometry matrix mapping from magentized voxel cells to the receivers for source pp
		#
		# INPUTS:
		# xyzc: N by 3 array containing cell center locations
		# xyzh: N by 3 array containing cell dimensions
		# pp: Source index

		srcObj = self.survey.srcList[pp]

		N = np.shape(xyzc)[0] # Number of cells
		K = srcObj.nRx # Number of receiver in all rxList

		ax = np.reshape(xyzc[:,0] - xyzh[:,0]/2, (1,N))
		bx = np.reshape(xyzc[:,0] + xyzh[:,0]/2, (1,N))
		ay = np.reshape(xyzc[:,1] - xyzh[:,1]/2, (1,N))
		by = np.reshape(xyzc[:,1] + xyzh[:,1]/2, (1,N))
		az = np.reshape(xyzc[:,2] - xyzh[:,2]/2, (1,N))
		bz = np.reshape(xyzc[:,2] + xyzh[:,2]/2, (1,N))

		G = np.zeros((K,3*N))
		C = -(1/(4*np.pi))
		eps = 1e-10

		COUNT = 0

		for qq in range(0,len(srcObj.rxList)):

			rxObj = srcObj.rxList[qq]
			dComp = rxObj.fieldComp
			locs = rxObj.locs
			M = np.shape(locs)[0]

			if dComp is 'x':
				for rr in range(0,M):
					u1 = locs[rr,0] - ax
					u1[np.abs(u1) < 1e-10] =  np.min(xyzh[:,0])/1000 
					u2 = locs[rr,0] - bx 
					u2[np.abs(u2) < 1e-10] = -np.min(xyzh[:,0])/1000 
					v1 = locs[rr,1] - ay 
					v1[np.abs(v1) < 1e-10] =  np.min(xyzh[:,1])/1000 
					v2 = locs[rr,1] - by 
					v2[np.abs(v2) < 1e-10] = -np.min(xyzh[:,1])/1000 
					w1 = locs[rr,2] - az 
					w1[np.abs(w1) < 1e-10] =  np.min(xyzh[:,2])/1000 
					w2 = locs[rr,2] - bz 
					w2[np.abs(w2) < 1e-10] = -np.min(xyzh[:,2])/1000

					Gxx = np.arctan((v1*w1)/(u1*np.sqrt(u1**2+v1**2+w1**2)+eps)) \
					- np.arctan((v1*w1)/(u2*np.sqrt(u2**2+v1**2+w1**2)+eps)) \
					+ np.arctan((v2*w1)/(u2*np.sqrt(u2**2+v2**2+w1**2)+eps)) \
					- np.arctan((v2*w1)/(u1*np.sqrt(u1**2+v2**2+w1**2)+eps)) \
					+ np.arctan((v2*w2)/(u1*np.sqrt(u1**2+v2**2+w2**2)+eps)) \
					- np.arctan((v1*w2)/(u1*np.sqrt(u1**2+v1**2+w2**2)+eps)) \
					+ np.arctan((v1*w2)/(u2*np.sqrt(u2**2+v1**2+w2**2)+eps)) \
					- np.arctan((v2*w2)/(u2*np.sqrt(u2**2+v2**2+w2**2)+eps))

					Gyx = np.log(np.sqrt(u1**2+v1**2+w1**2)-w1) \
					- np.log(np.sqrt(u2**2+v1**2+w1**2)-w1) \
					+ np.log(np.sqrt(u2**2+v2**2+w1**2)-w1) \
					- np.log(np.sqrt(u1**2+v2**2+w1**2)-w1) \
					+ np.log(np.sqrt(u1**2+v2**2+w2**2)-w2) \
					- np.log(np.sqrt(u1**2+v1**2+w2**2)-w2) \
					+ np.log(np.sqrt(u2**2+v1**2+w2**2)-w2) \
					- np.log(np.sqrt(u2**2+v2**2+w2**2)-w2)

					Gzx = np.log(np.sqrt(u1**2+v1**2+w1**2)-v1) \
					- np.log(np.sqrt(u2**2+v1**2+w1**2)-v1) \
					+ np.log(np.sqrt(u2**2+v2**2+w1**2)-v2) \
					- np.log(np.sqrt(u1**2+v2**2+w1**2)-v2) \
					+ np.log(np.sqrt(u1**2+v2**2+w2**2)-v2) \
					- np.log(np.sqrt(u1**2+v1**2+w2**2)-v1) \
					+ np.log(np.sqrt(u2**2+v1**2+w2**2)-v1) \
					- np.log(np.sqrt(u2**2+v2**2+w2**2)-v2)

					G[COUNT,:] = C*np.c_[Gxx,Gyx,Gzx]
					COUNT = COUNT + 1

			elif dComp is 'y':
				for rr in range(0,M):
					u1 = locs[rr,0] - ax
					u1[np.abs(u1) < 1e-10] =  np.min(xyzh[:,0])/1000 
					u2 = locs[rr,0] - bx 
					u2[np.abs(u2) < 1e-10] = -np.min(xyzh[:,0])/1000 
					v1 = locs[rr,1] - ay 
					v1[np.abs(v1) < 1e-10] =  np.min(xyzh[:,1])/1000 
					v2 = locs[rr,1] - by 
					v2[np.abs(v2) < 1e-10] = -np.min(xyzh[:,1])/1000 
					w1 = locs[rr,2] - az 
					w1[np.abs(w1) < 1e-10] =  np.min(xyzh[:,2])/1000 
					w2 = locs[rr,2] - bz 
					w2[np.abs(w2) < 1e-10] = -np.min(xyzh[:,2])/1000 

					Gxy = np.log(np.sqrt(u1**2+v1**2+w1**2)-w1) \
					- np.log(np.sqrt(u2**2+v1**2+w1**2)-w1) \
					+ np.log(np.sqrt(u2**2+v2**2+w1**2)-w1) \
					- np.log(np.sqrt(u1**2+v2**2+w1**2)-w1) \
					+ np.log(np.sqrt(u1**2+v2**2+w2**2)-w2) \
					- np.log(np.sqrt(u1**2+v1**2+w2**2)-w2) \
					+ np.log(np.sqrt(u2**2+v1**2+w2**2)-w2) \
					- np.log(np.sqrt(u2**2+v2**2+w2**2)-w2)

					Gyy = np.arctan((u1*w1)/(v1*np.sqrt(u1**2+v1**2+w1**2)+eps)) \
					- np.arctan((u2*w1)/(v1*np.sqrt(u2**2+v1**2+w1**2)+eps)) \
					+ np.arctan((u2*w1)/(v2*np.sqrt(u2**2+v2**2+w1**2)+eps)) \
					- np.arctan((u1*w1)/(v2*np.sqrt(u1**2+v2**2+w1**2)+eps)) \
					+ np.arctan((u1*w2)/(v2*np.sqrt(u1**2+v2**2+w2**2)+eps)) \
					- np.arctan((u1*w2)/(v1*np.sqrt(u1**2+v1**2+w2**2)+eps)) \
					+ np.arctan((u2*w2)/(v1*np.sqrt(u2**2+v1**2+w2**2)+eps)) \
					- np.arctan((u2*w2)/(v2*np.sqrt(u2**2+v2**2+w2**2)+eps)) 

					Gzy = np.log(np.sqrt(u1**2+v1**2+w1**2)-u1) \
					- np.log(np.sqrt(u2**2+v1**2+w1**2)-u2) \
					+ np.log(np.sqrt(u2**2+v2**2+w1**2)-u2) \
					- np.log(np.sqrt(u1**2+v2**2+w1**2)-u1) \
					+ np.log(np.sqrt(u1**2+v2**2+w2**2)-u1) \
					- np.log(np.sqrt(u1**2+v1**2+w2**2)-u1) \
					+ np.log(np.sqrt(u2**2+v1**2+w2**2)-u2) \
					- np.log(np.sqrt(u2**2+v2**2+w2**2)-u2)

					G[COUNT,:] = C*np.c_[Gxy,Gyy,Gzy]
					COUNT = COUNT + 1

			elif dComp is 'z':
				for rr in range(0,M):
					u1 = locs[rr,0] - ax
					u1[np.abs(u1) < 1e-10] =  np.min(xyzh[:,0])/1000 
					u2 = locs[rr,0] - bx 
					u2[np.abs(u2) < 1e-10] = -np.min(xyzh[:,0])/1000 
					v1 = locs[rr,1] - ay 
					v1[np.abs(v1) < 1e-10] =  np.min(xyzh[:,1])/1000 
					v2 = locs[rr,1] - by 
					v2[np.abs(v2) < 1e-10] = -np.min(xyzh[:,1])/1000 
					w1 = locs[rr,2] - az 
					w1[np.abs(w1) < 1e-10] =  np.min(xyzh[:,2])/1000 
					w2 = locs[rr,2] - bz 
					w2[np.abs(w2) < 1e-10] = -np.min(xyzh[:,2])/1000

					Gxz = np.log(np.sqrt(u1**2+v1**2+w1**2)-v1) \
					- np.log(np.sqrt(u2**2+v1**2+w1**2)-v1) \
					+ np.log(np.sqrt(u2**2+v2**2+w1**2)-v2) \
					- np.log(np.sqrt(u1**2+v2**2+w1**2)-v2) \
					+ np.log(np.sqrt(u1**2+v2**2+w2**2)-v2) \
					- np.log(np.sqrt(u1**2+v1**2+w2**2)-v1) \
					+ np.log(np.sqrt(u2**2+v1**2+w2**2)-v1) \
					- np.log(np.sqrt(u2**2+v2**2+w2**2)-v2) 

					Gyz = np.log(np.sqrt(u1**2+v1**2+w1**2)-u1) \
					- np.log(np.sqrt(u2**2+v1**2+w1**2)-u2) \
					+ np.log(np.sqrt(u2**2+v2**2+w1**2)-u2) \
					- np.log(np.sqrt(u1**2+v2**2+w1**2)-u1) \
					+ np.log(np.sqrt(u1**2+v2**2+w2**2)-u1) \
					- np.log(np.sqrt(u1**2+v1**2+w2**2)-u1) \
					+ np.log(np.sqrt(u2**2+v1**2+w2**2)-u2) \
					- np.log(np.sqrt(u2**2+v2**2+w2**2)-u2) 

					Gzz = - np.arctan((v1*w1)/(u1*np.sqrt(u1**2+v1**2+w1**2)+eps)) \
					+ np.arctan((v1*w1)/(u2*np.sqrt(u2**2+v1**2+w1**2)+eps)) \
					- np.arctan((v2*w1)/(u2*np.sqrt(u2**2+v2**2+w1**2)+eps)) \
					+ np.arctan((v2*w1)/(u1*np.sqrt(u1**2+v2**2+w1**2)+eps)) \
					- np.arctan((v2*w2)/(u1*np.sqrt(u1**2+v2**2+w2**2)+eps)) \
					+ np.arctan((v1*w2)/(u1*np.sqrt(u1**2+v1**2+w2**2)+eps)) \
					- np.arctan((v1*w2)/(u2*np.sqrt(u2**2+v1**2+w2**2)+eps)) \
					+ np.arctan((v2*w2)/(u2*np.sqrt(u2**2+v2**2+w2**2)+eps))

					Gzz = Gzz - np.arctan((u1*w1)/(v1*np.sqrt(u1**2+v1**2+w1**2)+eps)) \
					+ np.arctan((u2*w1)/(v1*np.sqrt(u2**2+v1**2+w1**2)+eps)) \
					- np.arctan((u2*w1)/(v2*np.sqrt(u2**2+v2**2+w1**2)+eps)) \
					+ np.arctan((u1*w1)/(v2*np.sqrt(u1**2+v2**2+w1**2)+eps)) \
					- np.arctan((u1*w2)/(v2*np.sqrt(u1**2+v2**2+w2**2)+eps)) \
					+ np.arctan((u1*w2)/(v1*np.sqrt(u1**2+v1**2+w2**2)+eps)) \
					- np.arctan((u2*w2)/(v1*np.sqrt(u2**2+v1**2+w2**2)+eps)) \
					+ np.arctan((u2*w2)/(v2*np.sqrt(u2**2+v2**2+w2**2)+eps))

					G[COUNT,:] = C*np.c_[Gxz,Gyz,Gzz]
					COUNT = COUNT + 1

		return np.matrix(G)











#######################################################################################
# VRM CHARACTERISTIC DECAY FORMULATION (SINGLE MODEL PARAMETER AND ALLOWS INVERSION)
#######################################################################################


class LinearFWD(BaseProblemVRM):

	def __init__(self, mesh, **kwargs):
		super(LinearFWD,self).__init__(mesh, **kwargs)



	def fields(self, mod, **kwargs):

		topoInd = mod != 0 # Only predict data from non-zero model values unless specified

		
		# GET CELL INFORMATION FOR FORWARD MODELING
		meshObj = self.mesh
		xyzc = meshObj.gridCC[topoInd,:]
		xyzh = meshObj.gridH[topoInd,:]
		# xyzh = self.fcngridH(meshObj) # <-- Temporary method was created to do this
		# xyzh = xyzh[topoInd,:]
		P = sp.diags(np.ones(len(mod)), format='csr')
		P = P[topoInd,:]

		# GET A MATRIX
		A = []
		for pp in range(0,self.survey.nSrc):

			# Create initial A matrix
			G   = self.getGeometryMatrix(xyzc, xyzh, pp)
			H0  = self.getH0matrix(xyzc, pp)
			A[pp] = G*H0

			# Refine A matrix
			refFact = self.refFact
			refRadius = self.refRadius

			if refFact > 0:

				srcObj = self.survey.srcList[pp]
				refFlag = srcObj._getRefineFlags(xyzc, refFact, refRadius)

				for qq in range(0,refFact):

					# Get subset mesh
					# Get subset A matrix











		A = np.vstack(A)

		return A


	# def _getSubsetMesh(self):

	# def_getSubsetAmatrix(self):





























