FROM centos:7

USER root
ENV JAVA_HOME /usr/lib/jvm/java
RUN yum -y install java-1.8.0-openjdk-devel && yum clean all

RUN yum update -y && yum -y install xmlstarlet saxon augeas bsdtar unzip && yum clean all

RUN groupadd -r jboss -g 1000 && useradd -u 1000 -r -g jboss -m -d /opt/jboss -s /sbin/nologin -c "JBoss user" jboss && \
    chmod 755 /opt/jboss
USER jboss

WORKDIR /opt/jboss

USER root

RUN mkdir -p /deployments

# JAVA_APP_DIR is used by run-java.sh for finding the binaries
ENV JAVA_APP_DIR=/deployments \
    JAVA_MAJOR_VERSION=8


# Agent bond including Jolokia and jmx_exporter
ADD agent-bond-opts /opt/run-java-options
RUN mkdir -p /opt/agent-bond \
 && curl http://central.maven.org/maven2/io/fabric8/agent-bond-agent/1.2.0/agent-bond-agent-1.2.0.jar \
          -o /opt/agent-bond/agent-bond.jar \
 && chmod 444 /opt/agent-bond/agent-bond.jar \
 && chmod 755 /opt/run-java-options
ADD jmx_exporter_config.yml /opt/agent-bond/
EXPOSE 8778 9779

# Add run script as /deployments/run-java.sh and make it executable
COPY run-java.sh /deployments/
RUN chmod 755 /deployments/run-java.sh



# Run under user "jboss" and prepare for be running
# under OpenShift, too
RUN chown -R jboss /deployments \
  && usermod -g root -G `id -g jboss` jboss \
  && chmod -R "g+rwX" /deployments \
  && chown -R jboss:root /deployments

USER jboss


CMD [ "/deployments/run-java.sh" ]







ENV JAVA_APP_JAR guestbook-service-swarm.jar
ENV AB_OFF true
ENV JAVA_OPTIONS -Xmx512m

EXPOSE 8080

ADD target/guestbook-service-swarm.jar /deployments/
