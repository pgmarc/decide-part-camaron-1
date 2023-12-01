import json
import tempfile
import os
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from .models import Census
from base import mods
from base.tests import BaseTestCase
from datetime import datetime, timedelta, timezone

class BaseExportTestCase(TestCase):
    def setUp(self):
        #Creamos 4 censos distintos
        self.census_data = [
            {
                'voting_id': i,
                'voter_id': i,
            }
            for i in range(1, 5) 
        ]
        #Creamos los censos con datos de census_data
        self.census_create = [Census.objects.create(**data) for data in self.census_data]
        
        #Verificamos que cada censo creado, verifica que voter_id y voting_id son i+1
        for i, censo in enumerate(self.census_create):
            self.assertEqual(censo.voting_id, i + 1)
            self.assertEqual(censo.voter_id, i + 1)
        
    def tearDown(self):
        Census.objects.all().delete()

class CensusTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.census = Census(voting_id=1, voter_id=1)
        self.census.save()

    def tearDown(self):
        super().tearDown()
        self.census = None

    def test_check_vote_permissions(self):
        response = self.client.get('/census/{}/?voter_id={}'.format(1, 2), format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), 'Invalid voter')

        response = self.client.get('/census/{}/?voter_id={}'.format(1, 1), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Valid voter')

    def test_list_voting(self):
        response = self.client.get('/census/?voting_id={}'.format(1), format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.get('/census/?voting_id={}'.format(1), format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.get('/census/?voting_id={}'.format(1), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'voters': [1]})

    def test_add_new_voters_conflict(self):
        data = {'voting_id': 1, 'voters': [1]}
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 409)

    def test_add_new_voters(self):
        data = {'voting_id': 2, 'voters': [1,2,3,4]}
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(data.get('voters')), Census.objects.count() - 1)

    def test_destroy_voter(self):
        data = {'voters': [1]}
        response = self.client.delete('/census/{}/'.format(1), data, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(0, Census.objects.count())


class CensusTest(StaticLiveServerTestCase):
    def setUp(self):
        #Load base test functionality for decide
        self.base = BaseTestCase()
        self.base.setUp()

        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)

        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.driver.quit()

        self.base.tearDown()
    
    def createCensusSuccess(self):
        self.cleaner.get(self.live_server_url+"/admin/login/?next=/admin/")
        self.cleaner.set_window_size(1280, 720)

        self.cleaner.find_element(By.ID, "id_username").click()
        self.cleaner.find_element(By.ID, "id_username").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").click()
        self.cleaner.find_element(By.ID, "id_password").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").send_keys("Keys.ENTER")

        self.cleaner.get(self.live_server_url+"/admin/census/census/add")
        now = datetime.now()
        self.cleaner.find_element(By.ID, "id_voting_id").click()
        self.cleaner.find_element(By.ID, "id_voting_id").send_keys(now.strftime("%m%d%M%S"))
        self.cleaner.find_element(By.ID, "id_voter_id").click()
        self.cleaner.find_element(By.ID, "id_voter_id").send_keys(now.strftime("%m%d%M%S"))
        self.cleaner.find_element(By.NAME, "_save").click()

        self.assertTrue(self.cleaner.current_url == self.live_server_url+"/admin/census/census")

    def createCensusEmptyError(self):
        self.cleaner.get(self.live_server_url+"/admin/login/?next=/admin/")
        self.cleaner.set_window_size(1280, 720)

        self.cleaner.find_element(By.ID, "id_username").click()
        self.cleaner.find_element(By.ID, "id_username").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").click()
        self.cleaner.find_element(By.ID, "id_password").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").send_keys("Keys.ENTER")

        self.cleaner.get(self.live_server_url+"/admin/census/census/add")

        self.cleaner.find_element(By.NAME, "_save").click()

        self.assertTrue(self.cleaner.find_element_by_xpath('/html/body/div/div[3]/div/div[1]/div/form/div/p').text == 'Please correct the errors below.')
        self.assertTrue(self.cleaner.current_url == self.live_server_url+"/admin/census/census/add")

    def createCensusValueError(self):
        self.cleaner.get(self.live_server_url+"/admin/login/?next=/admin/")
        self.cleaner.set_window_size(1280, 720)

        self.cleaner.find_element(By.ID, "id_username").click()
        self.cleaner.find_element(By.ID, "id_username").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").click()
        self.cleaner.find_element(By.ID, "id_password").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").send_keys("Keys.ENTER")

        self.cleaner.get(self.live_server_url+"/admin/census/census/add")
        now = datetime.now()
        self.cleaner.find_element(By.ID, "id_voting_id").click()
        self.cleaner.find_element(By.ID, "id_voting_id").send_keys('64654654654654')
        self.cleaner.find_element(By.ID, "id_voter_id").click()
        self.cleaner.find_element(By.ID, "id_voter_id").send_keys('64654654654654')
        self.cleaner.find_element(By.NAME, "_save").click()

        self.assertTrue(self.cleaner.find_element_by_xpath('/html/body/div/div[3]/div/div[1]/div/form/div/p').text == 'Please correct the errors below.')
        self.assertTrue(self.cleaner.current_url == self.live_server_url+"/admin/census/census/add")

class ExportCensusJSONTest(BaseExportTestCase):
    def testExportListJson(self):
        url_exportacion = reverse('export_census_json')
        response = self.client.get(url_exportacion)
        self.assertEqual(response.status_code, 200)

        datos_exportados = json.loads(response.content.decode('utf-8'))

        self.assertIsInstance(datos_exportados, list)
        self.assertEqual(len(datos_exportados), len(self.census_create))

        # Iteramos a través de cada elemento exportado y comparamos con la instancia de censo correspondiente
        for indice, datos_censo_exportado in enumerate(datos_exportados):
            if indice < len(self.census_create):
                self.assertCheckCreatedCensusDataEqualsCensusData(datos_censo_exportado, self.census_create[indice])

    def testExportedJsonFile(self):
        url_exportacion = reverse('export_census_json')
        response = self.client.get(url_exportacion)
        self.assertEqual(response.status_code, 200)

        datos_respuesta = json.loads(response.content.decode('utf-8'))

        # Creamos un archivo temporal con extensión .json para almacenar los datos exportados
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w+b') as archivo_temporal:
            archivo_temporal.write(json.dumps(datos_respuesta, indent=2, default=str).encode('utf-8'))
            ruta_archivo_temporal = archivo_temporal.name

        self.assertTrue(os.path.exists(ruta_archivo_temporal))

        # Leemos los datos guardados desde el archivo JSON temporal
        with open(ruta_archivo_temporal, 'r', encoding='utf-8') as archivo_json_temporal:
            datos_guardados = json.load(archivo_json_temporal)

        # Comparamos cada conjunto de datos guardados con las instancias del censo creado
        for indice, datos_censo_guardado in enumerate(datos_guardados):
            if indice < len(self.census_create):
                self.assertCheckCreatedCensusDataEqualsCensusData(datos_censo_guardado, self.census_create[indice])

        os.remove(ruta_archivo_temporal)

    def assertCheckCreatedCensusDataEqualsCensusData(self, exported_data, census_create):
        self.assertEqual(exported_data['voting_id'], census_create.voting_id)
        self.assertEqual(exported_data['voter_id'], census_create.voter_id)
        expected_keys = ['voting_id', 'voter_id']
        self.assertCountEqual(exported_data.keys(), expected_keys)
