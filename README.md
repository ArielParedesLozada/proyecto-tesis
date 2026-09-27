# PROYECTO DE INVESTIGACION

Crear un sistema web de prediccion y control operacional para una maquina en Plasticaucho

## OBJETIVO

Desarrollar un sistema de prediccion en base alos registros obtenidos de la maquina de Plasticaucho para tener un control operacional sobre la energia

## REQUERIMIENTOS FUNCIONALES

- Definir una arquitectura, capas y demas cosas para poder entrenar modelos de IA para la prediccion energetica
- Tener un modelo que, dadas las condiciones actuales de la maquina, pueda predecir el consumo energetico del siguiente turno
- Poder ver la prediccion del consumo energetico sobrepuesta sobre el consumo real
- En esa prediccion del consumo, ver dos lineas, una superior y otra inferior, para tener limites de consumo energetico
- Las lineas de consumo energetico se calculan mediante formulas estadisticas

## ESTRUCTURA

```console
src/
    data/
        # Capa de datos sencilla. AUN NO REGISTRO HISTORICOS DE CONSUMO, ASI QUE ESTA COSA NO INTERACTURARIA CON UNA DB AUN
    domain/
        # Dominio de la aplicacion
        models/
            Registro que se obtiene desde la maquina (por ahora, solo seria un mock)

    presentation/
        # Vistas de la aplicacion
```

## TECHSTACK

- Visible en devenv.nix