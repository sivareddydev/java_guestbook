
from collections import OrderedDict
import xml.etree.ElementTree as ET
import os

ns = {"pom": "http://maven.apache.org/POM/4.0.0"}
result = OrderedDict()
cwd = os.getcwd()


def docker_image(root):
    print ("Checking if component is docker image")
    build = root.find("./pom:build", ns)

    if build is None:
        return None

    plugins = build.findall('./pom:plugins/pom:plugin', ns)

    found_plugin = None
    for plugin in plugins:
        print ("-- Found plugin: ", plugin.find("./pom:artifactId", ns).text)
        if plugin.find("./pom:artifactId", ns).text == "docker-maven-plugin":
            found_plugin = plugin
            break

    print ("Processing profiles")
    profiles = root.find("./pom:profiles", ns)
    if profiles is not None:
        for profile in profiles:
            profile_build = profile.find("./pom:build", ns)
            if profile_build is None:
                continue
            profile_plugins = profile_build.findall("./pom:plugins/pom:plugin")
            if profile_plugins is None:
                continue
            for profile_plugin in profile_plugins:
                profile_artifact = profile_plugin.find("./pom:artifactId", ns)
                print ("-- Found profile plugin: ", profile_artifact.text)
                if profile_artifact.text == "docker-maven-plugin":
                    found_plugin = profile_plugin
                    break

    if found_plugin is None:
        return None

    goal = found_plugin.find(
        "./pom:executions/pom:execution/pom:goals/pom:goal", ns)
    if goal is not None and goal.text == "build":
        image = found_plugin.find(
            "./pom:configuration/pom:images/pom:image", ns)
        print ("Docker image detected with name ", image.find("./pom:name", ns).text)  # noqa
        return image.find("./pom:name", ns).text

    return None


def parse_pom(inherit_group, inherit_artifact, inherit_version, inherit_docker_namespace):  # noqa
    file = os.path.join(os.getcwd(), "pom.xml")
    print ("parsing: {0}".format(file))
    tree = ET.parse(file)
    root = tree.getroot()

    found_group = root.find("./pom:groupId", ns)
    group_id = found_group.text if found_group is not None else inherit_group

    found_artifact = root.find("./pom:artifactId", ns)
    artifact_id = found_artifact.text if found_artifact is not None else inherit_artifact  # noqa

    found_version = root.find("./pom:version", ns)
    version = found_version.text if found_version is not None else inherit_version  # noqa

    found_docker_namespace = root.find(
        './pom:properties/pom:docker-registry-namespace', ns)
    docker_namespace = found_docker_namespace.text if found_docker_namespace is not None else inherit_docker_namespace  # noqa

    # todo handle types
    found_packaging = root.find("./pom:packaging", ns)
    packaging = found_packaging.text if found_packaging is not None else "jar"

    print ("Buildset V1: Found component %s:%s%s:%s" % (group_id, artifact_id, version, packaging))  # noqa

    modules = root.findall("./pom:modules/pom:module", ns)
    if modules:
        print ("Buildset V1: Component has modules")
        for module in modules:
            current_dir = os.getcwd()
            os.chdir(os.path.join(current_dir, module.text))
            parse_pom(group_id, artifact_id, version, docker_namespace)
            os.chdir(current_dir)

        return group_id, version

    logicalname = '%s___%s' % (group_id, artifact_id)
    logicalname = logicalname.replace("net.apmoller.crb.", "")
    logicalname = logicalname.replace(".", "_")
    logicalname = logicalname.replace("-", "_")
    logicalname = logicalname.translate(None, '\t\n ')

    image = docker_image(root)

    if image:
        image = image.replace(
            "${docker-registry-internal}", "docker.cdpipeline.apmoller.net:10043")  # noqa
        image = image.replace("${docker-registry-namespace}", docker_namespace)
        image = image.replace("${project.artifactId}", artifact_id)
        artifact = "docker://%s:%s" % (image, version)
    else:
        artifact = "%s:%s:%s:%s" % (group_id, artifact_id, version, packaging)

    artifact = artifact.translate(None, '\t\n ')
    print ("Buildset V1: Resolved artifact entry %s=%s" % (logicalname,  artifact))  # noqa
    result[logicalname] = artifact

    return group_id, version


def write_result(group_id, version, group_suffix, artefact_id):
    """ This method will write out a properties file containing key value pairs
    to relevant nexus artefacts for a given build and a subsequent pom file
    to allow the properties file to be uploaded to nexus in the correct place

    Args:
        group_id: maven group_id fropm pom tree
        version: version from maven pom tree
        group_suffix: buildset or isolated deployment suffix
        artefact_id: maven artefact_id
    """
    parent_dir = os.path.join(os.getcwd(), "target", group_suffix)
    build_file = os.path.join(parent_dir, "build.properties")
    pom_file = os.path.join(parent_dir, "pom.xml")

    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    with open(build_file, 'w') as the_build_file:
        print ("Buildset V1: Writing properties file %s" % (build_file))
        for k, v in result.items():
            the_build_file.write("%s=%s\n" % (k, v))

    if group_suffix == "buildsetv1":
        # extract version in major.minor.patch format
        version = version.split("-")[0]
        version_parts = version.split(".")
        # set version to major.minor version
        version = "%s.%s" % (version_parts[0], version_parts[1])

        if "BUILDSET_VERSION_QUALIFIER" in os.environ:
            version = "%s-%s" % (version,
                                 os.environ['BUILDSET_VERSION_QUALIFIER'])

    group_name = "%s.%s" % (group_id, group_suffix)
    pom_content = """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>%s</groupId>
  <artifactId>%s</artifactId>
  <version>%s</version>
  <packaging>properties</packaging>
</project>""" % (group_name, artefact_id, version)

    with open(pom_file, 'w') as the_pom_file:
        print ("Buildset V1: Writing minimal pom with group=%s, version=%s" % (group_name, version))  # noqa
        the_pom_file.write(pom_content)


def write_result_isolated_pointerfile(group_id, version):
    """ This method will write out a pointer file containing a key value pair
    providing an isolated deployment version for a given build and a subsequent
    pom file to allow the pointer file to be uploaded to nexus in the correct
    place

    Args:
        group_id: maven group_id fropm pom tree
        version: version from maven pom tree
    """
    parent_dir = os.path.join(os.getcwd(), "target", "isolated-deploy-pointer")
    build_file = os.path.join(parent_dir, "build.properties")
    pom_file = os.path.join(parent_dir, "pom.xml")

    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    with open(build_file, 'w') as the_build_file:
        print ("Buildset V1: Writing pointer file for isolated deploy %s" % (build_file))  # noqa
        the_build_file.write("build_isolated_deploy=%s\n" % (version))

    # extract version in major.minor.patch format
    version = version.split("-")[0]
    version_parts = version.split(".")
    # set version to major.minor version
    version = "%s.%s" % (version_parts[0], version_parts[1])

    if "BUILDSET_VERSION_QUALIFIER" in os.environ:
        version = "%s-%s" % (version, os.environ['BUILDSET_VERSION_QUALIFIER'])
    group_name = "%s.isolated-deploy" % group_id
    pom_content = """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>%s</groupId>
  <artifactId>build</artifactId>
  <version>%s</version>
  <packaging>properties</packaging>
</project>""" % (group_name, version)

    with open(pom_file, 'w') as the_pom_file:
        print ("Buildset V1: Writing minimal pom for isolated-deploy pointer ")
        "file with group=%s, version=%s" % (group_name, version)
        the_pom_file.write(pom_content)


def main():
    print ("Buildset V1: Starting parsing")
    parent_group, version = parse_pom(None, None, None, None)
    print ("Parent group", parent_group, version)
    write_result(parent_group, version, "buildsetv1", "build")
    write_result(parent_group, version, "isolated-deploy", "artifacts")
    write_result_isolated_pointerfile(parent_group, version)


if __name__ == "__main__":
    main()


