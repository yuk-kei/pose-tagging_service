import math
import numpy as np


def pre_normalization(data, yaxis=[8, 1], xaxis=[2, 5]):  # original: zaxis=[0, 1], xaxis=[8, 4]

    def rotation_2D(theta):
        a = math.cos(theta)
        b = math.sin(theta)
        return np.array([[a, -b],
                         [b, a]])

    def unit_vector(vector):
        """ Returns the unit vector of the vector.  """
        return vector / np.linalg.norm(vector)

    def angle_between(v1, v2):
        """ Returns the angle in radians between vectors 'v1' and 'v2'::

                # >>> angle_between((1, 0, 0), (0, 1, 0))
                # 1.5707963267948966
                # >>> angle_between((1, 0, 0), (1, 0, 0))
                # 0.0
                # >>> angle_between((1, 0, 0), (-1, 0, 0))
                3.141592653589793
        """
        if np.abs(v1).sum() < 1e-6 or np.abs(v2).sum() < 1e-6:
            return 0
        v1_u = unit_vector(v1)
        v2_u = unit_vector(v2)
        return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))

    N, C, T, V, M = data.shape
    s = np.transpose(data, [0, 4, 2, 3, 1])  # N, C, T, V, M  to  N, M, T, V, C

    # print('convert the ntu format to tailored body25 format') #For two stream only. Can be delete.
    ss = np.zeros((N, M, T, 15, 2))
    for i_s, skeleton in enumerate(s):
        if skeleton.sum() == 0:
            continue
        skeleton = np.delete(skeleton, obj=[15, 16, 17, 18, 19, 20, 21, 22, 23, 24], axis=2)  # (2,300,15,3)
        skeleton = np.delete(skeleton, obj=[2], axis=3)  # (2,300,15,3)
        ss[i_s] = skeleton

    # print('parallel the bone between hip(jpt 0) and spine(jpt 1) of the first person to the y axis')
    for i_s, skeleton in enumerate(ss):
        if skeleton.sum() == 0:
            continue
        joint_bottom = skeleton[0, 0, yaxis[0]]  # top and bottom are reverse
        joint_top = skeleton[0, 0, yaxis[1]]
        # axis = np.cross(joint_top - joint_bottom, [0, 0, 1])
        angle = angle_between(-joint_top + joint_bottom, [0, 1])
        # print("joint top: ", joint_top)
        # print("joint bottom: ", joint_bottom)
        # print("vector: ", joint_top - joint_bottom)
        # print("angle: ", angle)
        # matrix_z = rotation_matrix(axis, angle)
        matrix_y = rotation_2D(angle)
        # print("matrix_y: ", matrix_y)
        for i_p, person in enumerate(skeleton):
            if person.sum() == 0:
                continue
            for i_f, frame in enumerate(person):
                if frame.sum() == 0:
                    continue
                for i_j, joint in enumerate(frame):
                    ss[i_s, i_p, i_f, i_j] = np.dot(matrix_y, joint.T)
                if i_f == 0:
                    # print("angle here: ", angle_between(ss[i_s, 0, 0, yaxis[0]]-ss[i_s, 0,0,yaxis[1]], [0,1]))
                    pass

    # print('parallel the bone between right shoulder(jpt 8) and left shoulder(jpt 4) of the first person to the x
    # axis')
    for i_s, skeleton in enumerate(ss):
        if skeleton.sum() == 0:
            continue
        joint_rshoulder = skeleton[0, 0, xaxis[0]]
        joint_lshoulder = skeleton[0, 0, xaxis[1]]
        # axis = np.cross(joint_rshoulder - joint_lshoulder, [1, 0])
        angle = angle_between(joint_rshoulder - joint_lshoulder, [-1, 0])
        # matrix_x = rotation_matrix(axis, angle)
        matrix_x = rotation_2D(angle)
        for i_p, person in enumerate(skeleton):
            if person.sum() == 0:
                continue
            for i_f, frame in enumerate(person):
                if frame.sum() == 0:
                    continue
                for i_j, joint in enumerate(frame):
                    ss[i_s, i_p, i_f, i_j] = np.dot(matrix_x, joint.T)

    data = np.transpose(ss, [0, 4, 2, 3, 1])
    return data
