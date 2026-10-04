from collections import defaultdict

from django.db import connections


def find_cycles(edges):
    """Return wait-for graph cycles from (waiting_transaction, blocking_transaction) pairs."""
    graph = defaultdict(list)
    for waiting, blocking in edges:
        graph[str(waiting)].append(str(blocking))
    cycles = []

    def visit(node, path):
        if node in path:
            cycles.append(path[path.index(node):] + [node])
            return
        for neighbour in graph.get(node, []):
            visit(neighbour, path + [node])

    for node in graph:
        visit(node, [])
    unique = []
    seen = set()
    for cycle in cycles:
        ring = cycle[:-1]
        rotations = [tuple(ring[index:] + ring[:index]) for index in range(len(ring))]
        key = min(rotations)
        if key not in seen:
            seen.add(key)
            unique.append(list(key) + [key[0]])
    return unique


def mysql_wait_for_edges(using="default"):
    """Read MySQL 8.4 InnoDB waits without killing a user transaction."""
    connection = connections[using]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT requesting_engine_transaction_id,
                   blocking_engine_transaction_id
            FROM performance_schema.data_lock_waits
            """
        )
        return cursor.fetchall()
