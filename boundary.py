from enum import Enum
import functools
import itertools
import operator


class Vect:
    """2D vector"""
    def __init__(self, x, y):
        self.x = x
        self.y = y


    def __hash__(self):
        return hash((self.x, self.y))


    def __repr__(self):
        return 'Vect({}, {})'.format(self.x, self.y)


    def __add__(self, other):
        return Vect(self.x + other.x, self.y + other.y)


    def __sub__(self, other):
        return Vect(self.x - other.x, self.y - other.y)


    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


    def __ne__(self, other):
        return not self.__eq__(other)


    def __lt__(self, other):
        return self.cmp_key() < other.cmp_key()


    def mult(self, m):
        return Vect(m * self.x, m * self.y)


    def cross_z(self, other):
        return self.x * other.y - self.y * other.x


    def l1_distance(self):
        return abs(self.x) + abs(self.y)


    def rotate(self, r):
        rmod = r % 4
        if rmod == 0:
            return Vect(self.x, self.y)
        elif rmod == 1:
            return Vect(-self.y, self.x)
        elif rmod == 2:
            return Vect(-self.x, -self.y)
        else:   # rmod == 3
            return Vect(self.y, -self.x)


    def cmp_key(self):
        return (self.x, self.y)


class Orientation(Enum):
    CLOCKWISE = 0
    COUNTERCLOCKWISE = 1
    UNDEFINED = 2


class Domain(Enum):
    INTERIOR = 0
    EXTERIOR = 1


class CompareLabels:
    @staticmethod
    def treat_none_as_regular_label(label_a, label_b):
        return label_a == label_b


    @staticmethod
    def treat_none_as_match_always(label_a, label_b):
        if label_a is None or label_b is None:
            return True
        else:
            return label_a == label_b


    @staticmethod
    def treat_none_as_match_never(label_a, label_b):
        if label_a is None or label_b is None:
            return False
        else:
            return label_a == label_b


class Boundary:
    def __init__(self):
        self.points = []
        self.labels = []


    def __repr__(self):
        return repr(list(zip(self.points, self.labels)))


    def __len__(self):
        assert len(self.points) == len(self.labels)
        return len(self.points)


    def append(self, vect, label = None):
        assert isinstance(vect, Vect)
        self.points.append(vect)
        self.labels.append(label)


    def set_labels(self, labels):
        assert len(labels) == len(self)
        self.labels = labels


    def __append(self, other):
        self.points += other.points
        self.labels += other.labels


    def __replace(self, other):
        self.points = other.points
        self.labels = other.labels


    def copy(self):
        other = Boundary()
        other.points = self.points.copy()
        other.labels = self.labels.copy()
        return other


    def __slice(self, i, j):
        imod = i % len(self)
        jmod = j % len(self)
        other = Boundary()
        if imod <= jmod:
            other.points = self.points[imod:jmod]
            other.labels = self.labels[imod:jmod]
        else:
            other.points = self.points[imod:] + self.points[:jmod]
            other.labels = self.labels[imod:] + self.labels[:jmod]
        return other


    def get_point(self, idx):
        current = idx % len(self)
        return self.points[current]


    def get_label(self, idx):
        current = idx % len(self)
        return self.labels[current]


    def get_edge(self, idx):
        current = idx % len(self)
        next = (idx + 1) % len(self)
        return self.points[next] - self.points[current]


    def iter_all(self, starting_idx = 0):
        imod = starting_idx % len(self)
        for idx in itertools.chain(range(imod, len(self)), range(0, imod)):
            yield (self.get_point(idx), self.get_edge(idx), self.get_label(idx))


    def iter_slice(self, i, j):
        imod = i % len(self)
        jmod = j % len(self)
        if imod <= jmod:
            range_indices = range(imod, jmod)
        else:
            range_indices = range(imod, jmod + len(self))
        for idx in range_indices:
            yield (self.get_point(idx), self.get_edge(idx), self.get_label(idx))


    @staticmethod
    def point_getter(iter):
        return map(operator.itemgetter(0), iter)


    @staticmethod
    def edge_getter(iter):
        return map(operator.itemgetter(1), iter)


    @staticmethod
    def label_getter(iter):
        return map(operator.itemgetter(2), iter)


    def orientation(self):
        def cumul_cross_z(cumul_tuple, edge):
            (sum, prev_edge) = cumul_tuple
            return (sum + prev_edge.cross_z(edge), edge)

        sum_cross_z, _ = functools.reduce(cumul_cross_z, (self.get_edge(idx) for idx in range(len(self))), (0, self.get_edge(-1)))
        if sum_cross_z > 0:
            return Orientation.COUNTERCLOCKWISE
        elif sum_cross_z < 0:
            return Orientation.CLOCKWISE
        else:
            return Orientation.UNDEFINED


    def is_unique_points(self):
        return len(set(self.points)) == len(self.points)


    def common_segments(self, other):
        """
        Returns the common segments between two boundaries as a list of tuples (i, j, l) where:
            i: start of the segment in this boundary
            j: start of the segment in the other boundary
            l: length of the segment

        Assumptions:
            The other boundary is outside of this boundary.
            The two boundaries have the same orientation.
        """
        assert self.is_unique_points()
        assert other.is_unique_points()
        # assert self.orientation() == other.orientation()

        # Identify common points and their respective indices. Those are considered "segments of length 0".
        self_points = dict((p, i) for (i, p) in enumerate(self.points))
        other_points = dict((p, i) for (i, p) in enumerate(other.points))
        common_points = set(self_points.keys()) & set(other_points.keys())
        common_segments_length_0 = sorted([(self_points[p], other_points[p], 0) for p in common_points])

        # Merge into actual segments
        def recurse_join_segments(remaining_length_0, cumul_segments = []):
            if len(remaining_length_0) == 0:
                return cumul_segments
            (prev_i, prev_j, _) = remaining_length_0[0]
            L = 0
            seg_index = 1
            while seg_index < len(remaining_length_0):
                (i, j, _) = remaining_length_0[seg_index]
                L += 1
                seg_index += 1
                if i != prev_i + L or j != (prev_j - L) % len(other_points):
                    L = L - 1
                    break
            cumul_segments.append((prev_i, (prev_j - L) % len(other_points), L))
            return recurse_join_segments(remaining_length_0[L+1:], cumul_segments)
        common_segments = recurse_join_segments(common_segments_length_0)

        # Deal with the index rollover on 'i' (we might want to join the first and last segments)
        if len(common_segments) >= 2:
            (i_first, j_first, L_first) = common_segments[0]
            (i_last, j_last, L_last) = common_segments[-1]
            if i_first == 0 and i_last + L_last == len(self_points) - 1 and (j_last - j_first) % len(other_points) == L_first + 1:
                common_segments = common_segments[1:]
                common_segments[-1] = (i_last, j_first, L_first + L_last + 1)

        return common_segments


    def find_matching_rotations(self, other, common_segment, cmp = CompareLabels.treat_none_as_regular_label):
        # assert self.orientation() == other.orientation()
        (i, j, L) = common_segment
        assert L > 0
        assert L < len(self)
        assert L < len(other)
        self_labels = self.__slice(i, i + L).labels
        self_labels.reverse()
        for r in range(len(other)):
            other_labels = other.__slice(j - r, j - r + L).labels
            assert len(other_labels) == len(self_labels)
            if all(cmp(*args) for args in zip(self_labels, other_labels)):
                yield r


    def merge(self, other, hint_common_segment = None):
        """Assuming the two boundaries share a unique common segment and have the same orientation, merge them into a single boundary"""
        if len(self) == 0:
            self.__replace(other)
        else:
            # assert self.orientation() == other.orientation()
            if hint_common_segment is None:
                segments = self.common_segments(other)
                assert len(segments) == 1
                (i, j, L) = segments[0]
            else:
                (i, j, L) = hint_common_segment
            assert L > 0
            assert L < len(self)
            assert L < len(other)
            merged = Boundary()
            merged.__append(other.__slice(j + L, j))
            merged.__append(self.__slice(i + L, i))
            assert len(merged) + 2 * L == len(self) + len(other)
            self.__replace(merged)
        return self


    def bottom_left(self):
        min_pt = min(self.points, key=Vect.cmp_key)
        return Vect(min_pt.x, min_pt.y)


    def rotate_to_start_with(self, point):
        idx = self.points.index(point)
        self.points = self.points[idx:] + self.points[:idx]
        self.labels = self.labels[idx:] + self.labels[:idx]


def from_edge(point, edge, orientation, domain):
    assert isinstance(point, Vect)
    assert isinstance(edge, Vect)
    assert isinstance(orientation, Orientation)
    assert isinstance(domain, Domain)
    border = Boundary()
    current_point = point
    r = 1 if orientation == Orientation.COUNTERCLOCKWISE else -1
    current_dir = edge if domain == Domain.INTERIOR else edge.rotate(-r)
    for i in range(4):
        border.append(current_point)
        current_point = current_point + current_dir
        current_dir = current_dir.rotate(r)
    return border


def get_tile(bottom_left, desc = [None, None, None, None]):
    """Instantiate the boundary of a unit square tile given the coordinates of its bottom left corner and a description"""
    assert isinstance(bottom_left, Vect)
    assert len(desc) == 4
    border = Boundary()
    for idx, delta in enumerate([Vect(0, 0), Vect(1, 0), Vect(1, 1), Vect(0, 1)]):
        border.append(bottom_left + delta, desc[idx])
    return border
