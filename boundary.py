from enum import Enum


class Vect:
    """2D vector"""
    def __init__(self, x, y):
        self.x = x
        self.y = y


    def __hash__(self):
        return hash((self.x, self.y))


    def __repr__(self):
        return  'Vect({}, {})'.format(self.x, self.y)


    def __add__(self, other):
        return Vect(self.x + other.x, self.y + other.y)


    def __sub__(self, other):
        return Vect(self.x - other.x, self.y - other.y)


    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


    def __ne__(self, other):
        return not self.__eq__(other)


    def mult(self, m):
        return Vect(m * self.x, m * self.y)


    def cross_z(self, other):
        return self.x * other.y - self.y * other.x


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


class Boundary:
    def __init__(self):
        self.points = []
        self.labels = []


    def __repr__(self):
        return repr(list(zip(self.points, self.labels)))


    def __len__(self):
        assert len(self.points) ==  len(self.labels)
        return len(self.points)


    def append(self, vect, label = None):
        assert isinstance(vect, Vect)
        self.points.append(vect)
        self.labels.append(label)


    def __append(self, other):
        self.points += other.points
        self.labels += other.labels


    def __replace(self, other):
        self.points = other.points
        self.labels = other.labels


    def slice(self, i, j):
        imod = i % len(self)
        jmod = j % len(self)
        result = Boundary()
        if imod < jmod:
            result.points = self.points[imod:jmod]
            result.labels = self.labels[imod:jmod]
        else:
            result.points = self.points[imod:] + self.points[:jmod]
            result.labels = self.labels[imod:] + self.labels[:jmod]
        return result


    def get_edge(self, idx):
        current = idx % len(self)
        next = (idx + 1) % len(self)
        return self.points[next] - self.points[current]


    def orientation(self):
        cross_z = sum(self.get_edge(i).cross_z(self.get_edge(i + 1)) for i in range(len(self)))
        if cross_z > 0:
            return Orientation.COUNTERCLOCKWISE
        elif cross_z < 0:
            return Orientation.CLOCKWISE
        else:
            return 0


    def is_unique_points(self):
        return len(set(self.points)) == len(self.points)


    def __points_and_indices(self):
        return dict([(self.points[i], i) for i in range(len(self))])


    def common_segments(self, other):
        """Returns the common segments between two boundaries as a list of tuples (i, j, l) where:
            i: start of the segment in this boundary
            j: start of the segment in the other boundary
            l: length of the segment
        """
        assert self.is_unique_points()
        assert other.is_unique_points()

        # Identify common points and their respective indices. Those are considered "segments of length 0".
        self_points = self.__points_and_indices()
        other_points = other.__points_and_indices()
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
            if i_first == 0 and i_last + L_last == len(self_points) - 1 and (j_last - j_first) % len(other_points) == L_first + L_last + 1:
                common_segments = common_segments[1:]
                common_segments[-1] = (i_last, j_first, L_first + L_last + 1)

        return common_segments


    def merge(self, other):
        """Assuming the two boundaries share a unique common segment and have the same orienation, merge them into a single boundary"""
        if len(self) == 0:
            self.__replace(other)
        else:
            segments = self.common_segments(other)
            assert len(segments) == 1
            assert self.orientation() == other.orientation()
            (i, j, L) = segments[0]
            merged = Boundary()
            merged.__append(other.slice(j + L, j))
            merged.__append(self.slice(i + L, i))
            assert len(merged) + 2 * L == len(self) + len(other)
            self.__replace(merged)


    def bottomleft(self):
        min_pt = min(self.points, key=Vect.cmp_key)
        return (min_pt.x, min_pt.y)


def from_edge(point, edge, orientation, domain):
    assert isinstance(edge, Vect)
    assert isinstance(orientation, Orientation)
    assert isinstance(domain, Domain)
    border = Boundary()
    current_point = point
    r = 1 if orientation == Orientation.COUNTERCLOCKWISE else -1
    current_dir = edge if domain == Domain.INTERIOR else edge.rotate(-r)
    for i in range(4):
        border.append(current_point, None)
        current_point = current_point + current_dir
        current_dir = current_dir.rotate(r)
    return border


def get_tile(i, j, desc = [None, None, None, None]):
    assert len(desc) == 4
    border = Boundary()
    border.append(Vect(i, j), desc[0])
    border.append(Vect(i+1, j), desc[1])
    border.append(Vect(i+1, j+1), desc[2])
    border.append(Vect(i, j+1), desc[3])
    return border
