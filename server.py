#!/usr/bin/env python3
"""
Serveur MCP qui génère automatiquement des outils depuis une spécification Swagger/OpenAPI
Compatible avec FastMCP 2.x
"""

import os
import json
import yaml
import requests
from typing import Any, Dict, Optional, get_type_hints
from urllib.parse import urlencode
import re

from fastmcp import FastMCP

# Initialiser FastMCP
mcp = FastMCP("swagger-mcp-server")

# Variables globales pour stocker la spec
swagger_spec: Optional[Dict[str, Any]] = None
base_url: str = ""
api_key: Optional[str] = None


def load_swagger_spec(swagger_url: str):
    """Charge la spécification Swagger/OpenAPI depuis l'URL"""
    global swagger_spec, base_url

    try:
        response = requests.get(swagger_url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')

        # Détecter si c'est du YAML ou JSON
        if 'yaml' in content_type or swagger_url.endswith(('.yaml', '.yml')):
            swagger_spec = yaml.safe_load(response.text)
        else:
            swagger_spec = response.json()

        # Définir l'URL de base
        if swagger_spec.get('servers') and len(swagger_spec['servers']) > 0:
            base_url = swagger_spec['servers'][0]['url']
        elif swagger_spec.get('host'):  # Swagger 2.0
            scheme = swagger_spec.get('schemes', ['https'])[0]
            base_path = swagger_spec.get('basePath', '')
            base_url = f"{scheme}://{swagger_spec['host']}{base_path}"

        #base_url = "https://api.openbrewerydb.org/v1/breweries"
        print(f"✅ API chargée: {swagger_spec['info']['title']} v{swagger_spec['info']['version']}", flush=True)
        print(f"📍 URL de base: {base_url}", flush=True)
        print(f"🔧 Génération des outils MCP...", flush=True)

    except Exception as e:
        print(f"❌ Erreur lors du chargement de la spec Swagger: {e}", flush=True)
        raise


def convert_path_to_tool_name(path: str, method: str) -> str:
    """Convertit un chemin d'API en nom d'outil MCP"""
    clean_path = path.strip('/')
    clean_path = re.sub(r'[{}]', '', clean_path)
    clean_path = clean_path.replace('/', '_')
    clean_path = re.sub(r'[^a-zA-Z0-9_]', '_', clean_path)
    return f"{method}_{clean_path}".lower()


def convert_openapi_type_to_python(openapi_type: str) -> type:
    """Convertit un type OpenAPI en type Python"""
    type_mapping = {
        'string': str,
        'integer': int,
        'number': float,
        'boolean': bool,
        'array': list,
        'object': dict,
    }
    return type_mapping.get(openapi_type, str)


def extract_parameters(operation: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Extrait les paramètres d'une opération et retourne un dict avec type et description"""
    params = {}

    # Paramètres de path, query, header
    if 'parameters' in operation:
        for param in operation['parameters']:
            param_name = param['name']
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', param.get('type', 'string'))

            params[param_name] = {
                'type': convert_openapi_type_to_python(param_type),
                'description': param.get('description', ''),
                'required': param.get('required', False)
            }

    # Corps de la requête (requestBody)
    if 'requestBody' in operation:
        content = operation['requestBody'].get('content', {})
        if 'application/json' in content:
            schema = content['application/json'].get('schema', {})
            if 'properties' in schema:
                required_fields = schema.get('required', [])
                for prop_name, prop_schema in schema['properties'].items():
                    prop_type = prop_schema.get('type', 'string')
                    params[prop_name] = {
                        'type': convert_openapi_type_to_python(prop_type),
                        'description': prop_schema.get('description', ''),
                        'required': prop_name in required_fields
                    }

    return params


def find_operation(tool_name: str) -> tuple[str, str, Dict[str, Any]]:
    """Trouve l'opération correspondant au nom d'outil"""
    if not swagger_spec:
        raise ValueError("Spec Swagger non chargée")

    for path, methods in swagger_spec['paths'].items():
        for method, operation in methods.items():
            if convert_path_to_tool_name(path, method) == tool_name:
                return path, method.upper(), operation

    raise ValueError(f"Outil {tool_name} non trouvé")


def execute_api_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Exécute l'appel API correspondant à l'outil"""
    path, method, operation = find_operation(tool_name)

    # Construire l'URL
    url = base_url + path
    print("######################################")
    print("URL appelée: " + url)
    print("######################################")

    path_params = {}
    query_params = {}
    body = {}

    # Séparer les paramètres
    if 'parameters' in operation:
        for param in operation['parameters']:
            param_name = param['name']
            if param_name in arguments:
                value = arguments[param_name]
                if param['in'] == 'path':
                    path_params[param_name] = value
                elif param['in'] == 'query':
                    query_params[param_name] = value

    # Remplacer les paramètres de path
    for key, value in path_params.items():
        url = url.replace(f'{{{key}}}', str(value))

    # Ajouter les paramètres de query
    if query_params:
        url += '?' + urlencode(query_params)

    # Préparer le corps de la requête
    if 'requestBody' in operation:
        for key, value in arguments.items():
            if key not in path_params and key not in query_params:
                body[key] = value

    # Préparer les headers
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    # Faire la requête
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body if body else None,
            timeout=30
        )

        # Essayer de parser en JSON
        try:
            result = response.json()
            return json.dumps(result, indent=2, ensure_ascii=False)
        except:
            return response.text

    except Exception as e:
        return json.dumps({'error': str(e)}, indent=2)


def create_tool_function(tool_name: str, description: str, params: Dict[str, Dict[str, Any]]):
    """Crée une fonction d'outil avec des paramètres explicites"""

    # Construire la signature de fonction dynamiquement
    # Séparer les paramètres requis et optionnels
    required_params = []
    optional_params = []
    annotations = {}

    for param_name, param_info in params.items():
        param_type = param_info['type']
        is_required = param_info['required']

        # Créer le paramètre avec type hint
        if is_required:
            required_params.append(f"{param_name}: {param_type.__name__}")
            annotations[param_name] = param_type
        else:
            optional_params.append(f"{param_name}: Optional[{param_type.__name__}] = None")
            annotations[param_name] = Optional[param_type]

    # Combiner les paramètres : requis d'abord, puis optionnels
    param_list = required_params + optional_params

    # Si pas de paramètres, créer une fonction sans args
    if not param_list:
        def tool_func() -> str:
            return execute_api_call(tool_name, {})

        tool_func.__name__ = tool_name
        tool_func.__doc__ = description
        return tool_func

    # Créer le code de la fonction
    args_assignment = '\n    '.join(
        f"if {p.split(':')[0].strip()} is not None: args['{p.split(':')[0].strip()}'] = {p.split(':')[0].strip()}"
        for p in param_list
    )

    func_code = f'''
def {tool_name}({', '.join(param_list)}) -> str:
    """{description}"""
    args = {{}}
    {args_assignment}
    return execute_api_call("{tool_name}", args)
'''

    # Exécuter le code pour créer la fonction
    local_vars = {
        'execute_api_call': execute_api_call,
        'Optional': Optional,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict
    }

    exec(func_code, local_vars)
    func = local_vars[tool_name]

    # Ajouter les annotations de type
    func.__annotations__ = {**annotations, 'return': str}

    return func


def register_tools():
    """Enregistre dynamiquement tous les outils depuis la spec Swagger"""
    if not swagger_spec or 'paths' not in swagger_spec:
        print("⚠️  Aucun outil à enregistrer", flush=True)
        return

    tool_count = 0

    for path, methods in swagger_spec['paths'].items():
        for method, operation in methods.items():
            if method.lower() not in ['get', 'post', 'put', 'patch', 'delete']:
                continue

            tool_name = convert_path_to_tool_name(path, method)
            description = operation.get('summary') or operation.get('description') or f"{method.upper()} {path}"
            params = extract_parameters(operation)

            # Créer et enregistrer la fonction avec des paramètres explicites
            tool_func = create_tool_function(tool_name, description, params)
            mcp.tool()(tool_func)

            tool_count += 1

    print(f"✨ {tool_count} outils générés avec succès!", flush=True)


#swagger_url = "https://petstore.swagger.io/v2/swagger.json"  # os.getenv('SWAGGER_URL')
#swagger_url = "https://raw.githubusercontent.com/internetarchive/openlibrary/refs/heads/master/static/openapi.json"
swagger_url="https://recherche-entreprises.api.gouv.fr/openapi.json"
load_swagger_spec(swagger_url)
register_tools()

def main():
    """Point d'entrée principal"""
    """
    global api_key

    swagger_url = "https://petstore.swagger.io/v2/swagger.json" #os.getenv('SWAGGER_URL')
    api_key = os.getenv('API_KEY')

    if not swagger_url:
        print("❌ Erreur: SWAGGER_URL doit être défini", flush=True)
        print("Usage: SWAGGER_URL=https://api.example.com/swagger.json python server_petstore.py", flush=True)
        return

    print("🚀 Démarrage du serveur MCP Swagger...", flush=True)

    # Charger la spec et enregistrer les outils
    load_swagger_spec(swagger_url)
    register_tools()

    print("✅ Serveur prêt!", flush=True)
    """
    # Démarrer le serveur
    mcp.run(transport="http", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()