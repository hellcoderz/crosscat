#!/bin/bash


# set default values
jenkins_home=/var/lib/jenkins/
user=sgeadmin
project_name=crosscat


# print script usage
usage() {
	cat <<EOF
useage: $0 options

	Set up jenkins

	OPTIONS:
	-h	Show this message
	-p	project_name=$project_name
	-u	user=$user
	-j	jenkins_home=$jenkins_home
EOF
exit
}

# Process the arguments
while getopts hp:u:j: opt
do
	case "$opt" in
		h) usage;;
		p) project_name=$OPTARG;;
		u) user=$OPTARG;;
		j) jenkins_home=$OPTARG;;
	esac
done

# set derived variables
jenkins_project=${jenkins_home}/workspace/$project_name
source_dir=/home/$user/$project_name/

# install jenkins
#   per http://pkg.jenkins-ci.org/debian-stable/
wget -q -O - http://pkg.jenkins-ci.org/debian-stable/jenkins-ci.org.key | sudo apt-key add -
sudo echo "deb http://pkg.jenkins-ci.org/debian-stable binary/" >> /etc/apt/sources.list
sudo apt-get update
sudo apt-get install -y jenkins
sudo apt-get update

# copy over the key script that will be run for tests
mkdir -p $jenkins_project
cp ${source_dir}/jenkins_script.sh $jenkins_project
chmod 777 $jenkins_project
chmod 777 ${jenkins_project}/jenkins_script.sh

# run some helper scripts
# set up headless matplotlib
mkdir -p ${jenkins_home}/.matplotlib
echo backend: Agg > ${jenkins_home}/.matplotlib/matplotlibrc
# set up password login, set password for jenkins user
bash ${source_dir}/install_scripts/setup_password_login.sh -u jenkins -p bigdata
# make sure jenkins api available for job setup automation
sudo -u $user zsh -c -i 'pip install jenkinsapi==0.1.13'


# make sure jenkins owns everythin
chown -R jenkins $jenkins_home

