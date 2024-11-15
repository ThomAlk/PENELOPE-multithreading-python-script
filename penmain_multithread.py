import subprocess
import os
import concurrent.futures
import shutil
from pathlib import Path

def run_penmain(command, directory, number):                   #Lance Penmain.exe
    try:
        if not os.path.isdir(directory):                          #Vérifie que le dossier existe
            raise FileNotFoundError(f"Dossier '{directory}' n'existe pas (Vérifier les noms)")
        
        with subprocess.Popen(command, cwd=directory, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:                # Affiche les messages dans le terminal

            for line in process.stdout:
                print('thread numéro ', number, ':', line, end='')    
            for line in process.stderr:
                print('thread numéro ', number, ':', line, end='')
    
        process.wait()
        return None

    except Exception as e:                        #Affiche les erreurs retournées
        print(f"Error: {e}")
        return None

def modify_nparticles(dir, number_thread, n, input_file):                       #Segmente le nombre de particules à simuler entre chaque thread
    try:
        file_path = os.path.join(dir, input_file)                  #Récupère l'emplacement du fichier d'entrée
        with open(file_path, 'r') as file:                         #Ouvre le fichier d'input
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("NSIMSH"):                           #Récupère la ligne du nombre de particules
                initial_number = int(float(line[7:10]))             #Récupère le nombre de particules
                number_by_thread = initial_number / number_thread   #Divise le nombre de particules par le nombre de thread utilisé
                lines[i] = f"NSIMSH {number_by_thread:.3e}\n"       #Change la valeur du nombre de particules
                break
        else:
            print("Ligne de particule non trouvée (Vérifier le dossier d'initialisation)")                 #Retourne l'erreur en cas de ligne non présente
            return False
        
        with open(file_path, 'w') as file:                          #Réécrit le fichier avec la nouvelle valeur
            file.writelines(lines)

        print(f"Division du nombre de particule du thread {n} réussi.")
        return True

    except Exception as e:                                           #Retourne si une erreur à eu lieu
        print(f"Erreur dans la division: {e}")
        return False

def fuse(file_paths, output_file, columns_to_add):      #Fusionne les fichiers produits en 1
    comment_lines = []
    data = []
    number_commentary=0
    with open(file_paths[0], 'r') as f:              #Ouvre le fichier du premier thread
        lines = f.readlines()
        
        #Identifie le commentaire au début de chaque fichier et le garde en mémoire afin de le garder dans le fichier final
        i = 0
        while lines[i].startswith(' #'):
            comment_lines.append(lines[i])
            i += 1
        

        data = [list(map(float, line.strip().split())) for line in lines[i:]]   #Récupère les données du premier thread
        number_commentary=i                                               #Garde en mémoire le nombre de ligne de commentaires


    for file_path in file_paths[1:]:     #Récupère les données pour tout les autres threads, en ignorant immédiatement les commentaires
        with open(file_path, 'r') as f:
            for idx, line in enumerate(lines[number_commentary:]):
                columns = list(map(float, line.strip().split()))
                for col_idx in columns_to_add:
                    data[idx][col_idx] += columns[col_idx]


    with open(output_file, 'w') as f:            #Ecrit le fichier fusioné
        for line in comment_lines:               #Ecrit les commentaire
            f.write(line)     
        for row in data:                         #Ecrit les données sous le formalisme original
            f.write(' '.join(f" {x:.6e}" for x in row) + '\n')

def create_directories(num_threads,original_directory, input_file):        #Créé des copies du dossier de base pour chaque thread
    directories = []
    for i in range(num_threads):
        dir = f"{original_directory}_copy_{i+1}"                #Crée le nom du dossier

        if os.path.exists(dir):                                         #Vérifie si des dossiers existes déjà. Si c'est le cas, les supprimes
            print(f"Le répertoire {dir} existe déjà. Suppression...")
            shutil.rmtree(dir)

        shutil.copytree(original_directory, dir)                 #Crée les dossiers étant des copies du dossier d'origine
        directories.append(dir)                                  
        modify_nparticles(dir, num_threads, i, input_file)                  #Lance la fonction de modification du nombre de particules
    return directories

def run_thread(command, original_directory, num_threads, input_file):       #Lance la même tache sur tout les threads
    directories= create_directories(num_threads,original_directory, input_file)             #Récupère le nom des fichiers copiées
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(run_penmain, command, dir, num): (dir, num) for (dir, num) in zip(directories, range(num_threads))}         #Lance penmain.exe dans chaque dossier, chacun sur un thread différent
        for future in concurrent.futures.as_completed(futures):
            temp_dir = futures[future]
            try:
                print(f"Dossier '{temp_dir}' s'est terminé sans erreur")              #Message de confirmation
            except Exception as e:
                print(f"Dossier '{temp_dir}' a rencontré une erreur: {e}")            #Retourne les erreurs
                
    files_names=('depth-dose.dat','x-dose.dat','y-dose.dat','z-dose.dat')     #Fusionne les fichiers suivant
    for name in files_names:
        file = [os.path.join(dir, name) for dir in directories]               #Récupère la position de chaque fichier 
        output_fused_file = os.path.join(original_directory, name)            #Produit la position du fichier fusioné
        fuse(file, output_fused_file, columns_to_add=[1, 2])                  #Produit le fichier fusioné


    return None


input_file= r'input.in'                              #Nom du fichier d'entré. Il est conseillé de ne pas le modifier et de changer le nom du fichier directement
command = r'.\penmain.exe < '+ input_file                         
directory = r'D:\Session Thom\Desktop\penelope\TP'        ########## A MODIFIER: emplacement du DOSSIER contenant tout les fichiers dont penmain.exe
threads = 1                                               ########## A MODIFIER: nombre de thread à utiliser. 

run_thread(command, directory, threads,input_file)                   #Lance le code
