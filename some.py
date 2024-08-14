"""
    Some test script for the Docker container
    
    This script runs on the Docker run command.
    It is used to test the Docker container.
"""

def some_function(): 
    print('Some function')


some_lambda = lambda: print('Some lambda')


if __name__ == '__main__':
    print('Run as a script')
    some_function()
    some_lambda()



# To copy a file inside/outside the container

# * Copy a file from the host to the container
# docker cp <container_id>:<path_inside_container> <path_outside_container>

# * Copy a file from the container to the host
# docker cp <path_inside_container> <container_id>:<path_outside_container>

