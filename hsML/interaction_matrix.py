from .numerov import radial_overlap
import numpy as np
import os.path
from tqdm import trange
from sympy.physics.wigner import clebsch_gordan, wigner_3j, wigner_6j

class interaction_matrix:
    """
    """
    def __init__(self, matrix_type, basis, **kwargs):
        self.type = matrix_type.lower()
        self.basis = basis
        self.num_states = len(self.basis.states)
        self.matrix = None
        self.populate_interaction_matrix(**kwargs)
    
    def populate_interaction_matrix(self, **kwargs):
        """ Populate interaction matrix.
        """
        tqdm_kwargs = dict([(x.replace('tqdm_', ''), kwargs[x]) for x in kwargs.keys() if 'tqdm_' in x])
        cache = kwargs.get('cache_matrices', True)
        if self.matrix is None or cache is False:
            if kwargs.get('load_matrices', False) and \
               check_matrix(self.type, self, **kwargs):
                self.matrix = load_matrix(self.type, self, **kwargs)
            else:
                self.matrix = np.zeros([self.num_states, self.num_states])
                for i in trange(self.num_states, desc='Calculating '+self.type+' terms', **tqdm_kwargs):
                    # off-diagonal elements only
                    for j in range(i, self.num_states):
                        self.matrix[i][j] = self.interaction_term(self.basis.states[i], self.basis.states[j], **kwargs)
                        # assume matrix is symmetric
                        self.matrix[j][i] = self.matrix[i][j]
                if kwargs.get('save_matrices', False):
                    save_matrix(self, **kwargs)  
        else:
            print('Using cached '+self.type+' matrix')
            
    def interaction_term(self, state_1, state_2, **kwargs):
        """ Calculate interaction term
        """
        if self.type == 'stark':
            return self.stark_interaction(state_1, state_2, **kwargs)
        elif self.type == 'zeeman':
            return self.zeeman_interaction(state_1, state_2, **kwargs)
        else:
            raise Exception("Interaction term '"+self.type+"' is not recognised.")
            
    def stark_interaction(self, state_1, state_2, **kwargs):
        """ Stark interaction between states |n1, l1, m> and |n2, l2, m>.
        """
        dL = state_2.L - state_1.L
        dM = state_2.ML - state_1.ML
        if (abs(dL) == 1) and (abs(dM) <= 1):
            p = kwargs.get('p', 1.0)
            # Stark interaction
            # TODO: Save the radial_overlap matrix, because this would allow fast recomputation for different angles
            return self.angular_overlap(state_1.L, state_2.L, state_1.ML, state_2.ML, **kwargs) * \
                   radial_overlap(state_1.n_eff, state_1.L, state_2.n_eff, state_2.L, p=p)
        else:
            return 0.0

    def angular_overlap(self, L_1, L_2, M_1, M_2, **kwargs):
        """ Angular overlap <l1, m| cos(theta) |l2, m>.
            For Stark interaction
        """
        dL = L_2 - L_1
        dM = M_2 - M_1
        L, M = int(L_1), int(M_1)
        field_angle = kwargs.get('field_angle', 0.0)
        frac_para = np.cos(field_angle*(np.pi/180))**2
        frac_perp = np.sin(field_angle*(np.pi/180))**2
        dM_allow = kwargs.get('dM_allow', [0])
        overlap = 0.0
        if not np.mod(field_angle, 180.0) == 90.0:
            if (dM == 0) and (dM in dM_allow):
                if dL == +1:
                    overlap += frac_para * (+(((L+1)**2-M**2)/((2*L+3)*(2*L+1)))**0.5)
                elif dL == -1:
                    overlap += frac_para * (+((L**2-M**2)/((2*L+1)*(2*L-1)))**0.5)
            elif (dM == +1) and (dM in dM_allow):
                if dL == +1:
                    overlap += frac_para * (-((L+M+2)*(L+M+1)/(2*(2*L+3)*(2*L+1)))**0.5)
                elif dL == -1:
                    overlap += frac_para * (+((L-M)*(L-M-1)/(2*(2*L+1)*(2*L-1)))**0.5)
            elif (dM == -1) and (dM in dM_allow):
                if dL == +1:
                    overlap += frac_para * (+((L-M+2)*(L-M+1)/(2*(2*L+3)*(2*L+1)))**0.5)
                elif dL == -1:
                    overlap += frac_para * (-((L+M)*(L+M-1)/(2*(2*L+1)*(2*L-1)))**0.5)

        if not np.mod(field_angle, 180.0) == 0.0:
            if dM == +1:
                if dL == +1:
                    overlap += frac_perp * (+(0.5*(-1)**(M-2*L))  * (((L+M+1)*(L+M+2))/((2*L+1)*(2*L+3)))**0.5)
                elif dL == -1:
                    overlap += frac_perp * (-(0.5*(-1)**(-M+2*L)) * (((L-M-1)*(L-M))  /((2*L-1)*(2*L+1)))**0.5)
            elif dM == -1:
                if dL == +1:
                    overlap += frac_perp * (+(0.5*(-1)**(M-2*L))  * (((L-M+1)*(L-M+2))/((2*L+1)*(2*L+3)))**0.5)
                elif dL == -1:
                    overlap += frac_perp * (-(0.5*(-1)**(-M+2*L)) * (((L+M-1)*(L+M))  /((2*L-1)*(2*L+1)))**0.5)
        return overlap    

    def zeeman_interaction(self, state_1, state_2, **kwargs):
        """ Zeeman interaction between two states.
        """
        if state_1 == state_2:
            return state_1.ML
        return 0.0
    
    def save_matrix(self, **kwargs):
        filename = self.type + '_' + self.filename()
        if self.type == 'stark':
            field_angle = kwargs.get('field_angle', 0.0)
            filename += '_angle_{}'.format(field_angle)

        save_dir = kwargs.get('matrices_dir', './')
        np.savez_compressed(save_dir+filename, matrix=self.matrix)
        print('Saved', self.type, 'matrix as, ')
        print('\t', save_dir+filename)

    def load_matrix(self, **kwargs):
        filename = self.type + '_' + self.filename()
        if self.type == 'stark':
            field_angle = kwargs.get('field_angle', 0.0)
            filename += '_angle_{}'.format(field_angle)
        filename += '.npz'

        load_dir = kwargs.get('matrices_dir', './')
        mat = np.load(load_dir+filename)
        print('Loaded', self.type, 'matrix from, ')
        print('\t', load_dir+filename)
        return mat['matrix']

    def check_matrix(self, **kwargs):
        filename = self.type + '_' + self.filename()
        if self.type == 'stark':
            field_angle = kwargs.get('field_angle', 0.0)
            filename += '_angle_{}'.format(field_angle)
        filename += '.npz'

        load_dir = kwargs.get('matrices_dir', './')
        return os.path.isfile(load_dir+filename) 
    
    def filename(self):
        return  'n=' + str(self.basis.params.n_min) + '-' + str(self.basis.params.n_max) + '_' + \
                'L_max=' + str(self.basis.params.L_max) + '_' + \
                'S=' + str(self.basis.params.S) + '_' + \
                'ML=' + str(self.basis.params.ML) + '_' + \
                'ML_max=' + str(self.basis.params.ML_max)