pipeline {

	agent any
	stages {

        stage("Get repo"){

			steps {
				sh "rm -rf ${WORKSPACE}/tropicalweather.web"
				sh "git clone https://github.com/workshopapps/tropicalweather.web.git"
				
			}
		}

		stage("build frontend"){

			steps {

				dir('tropicalweather.web/frontend') {
                    sh "npm install"
                    sh "CI=false npm run build"
        		}
			}
        }

        stage("build backend"){

			steps {
                sh "cd backend && sudo python3 -m pip install --upgrade pip"
                sh "cd backend && sudo pip install -r requirements.txt"
            }
        }

		stage("deploy") {
		
			steps {
				sh "sudo rm -rf /home/johnoni/tropicalweather.web"
				sh "sudo cp -r ${WORKSPACE}/tropicalweather.web /home/johnoni/"
				sh "sudo cp -r /home/johnoni/tropicalweather_env/logged /home/johnoni/tropicalweather.web/backend/logs"
				sh "sudo cp -r /home/johnoni/tropicalweather_env/app.env /home/johnoni/tropicalweather.web/backend/app/.env"
				sh "sudo cp -r /home/johnoni/tropicalweather_env/service-account-file.json /home/johnoni/tropicalweather.web/backend/app/"

				sh "sudo systemctl restart tropicalweatherf.service"
				sh "sudo systemctl restart tropicalweatherb.service"
            }
	    }
	}
}



