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

def modify_nparticles(dir, number_thread, input_file, n):                       #Segmente le nombre de particules à simuler entre chaque thread
    try:
        file_path = os.path.join(dir, input_file)                  #Récupère l'emplacement du fichier d'entrée
        with open(file_path, 'r') as file:                         #Ouvre le fichier d'input
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("RSEED"):                            #Récupère la ligne de graine
                lines[i] = f"RSEED  -{n+1} {n+1}\n"                   #Change la valeur des graines
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

def fuse(file_paths, output_file, num_threads ,columns_to_add):  # Fusionne les fichiers produits en 1
    comment_lines = []
    data = []
    number_commentary = 0

    for file_index, file_path in enumerate(file_paths):
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} n'existe pas.")
            continue

        with open(file_path, 'r') as f:
            lines = f.readlines()
            if file_index == 0: 
                # Identifie le commentaire au début de chaque fichier et le garde en mémoire afin de le garder dans le fichier final
                i = 0
                while lines[i].startswith(' #'):
                    comment_lines.append(lines[i])
                    i += 1

                # Récupère les données du premier fichier
                data = [list(map(float, line.strip().split())) for line in lines[i:]]
                number_commentary = i  # Garde en mémoire le nombre de lignes de commentaires
            else:
                for idx, line in enumerate(lines[number_commentary:]):  # Ignore les commentaires
                    columns = list(map(float, line.strip().split()))
                    for col_idx in columns_to_add:
                        data[idx][col_idx] += columns[col_idx]


    with open(output_file, 'w') as f:  # Ecrit le fichier fusioné
        for line in comment_lines:  # Ecrit les commentaires
            f.write(line)
        for row in data:  # Ecrit les données sous le formalisme original
            f.write(' '.join(f" {x/num_threads:.6e}" for x in row) + '\n')

def create_directories(num_threads, original_directory, input_file):
    directories = []
    dirs = [f"{original_directory}_copy_{i+1}" for i in range(num_threads)]           #Produit les noms de fichiers attendus

    dirs_found = [dir for dir in dirs if os.path.exists(dir)]                   #Produit la liste des fichiers trouvés
    

    #Le bloc suivant s'occupe de prendre en entrée le choix de l'utilisateur si des fichiers existant ont été trouvés
    if dirs_found:                                                         
        print("Les fichiers suivants existent déjà:")
        for dir in dirs_found:
            print(f"  - {dir}")
        user_input = input("Voulez-vous continuer la simulation existante ? (Y/n) ").strip().lower()
        print(user_input)
        
        if user_input == "y" or user_input=='':
            print("Reprise de la simulation...")
            return dirs                                #Sort immédiatement de la fonction si la simulation est poursuivie
    
        elif user_input == "n":
            print("Suppression des fichiers existant...")
            for dir in dirs_found:
                shutil.rmtree(dir)
        else:
            raise ValueError("Entrée invalide. Entrez 'y' ou entrée pour reprendre la simulation, ou 'n' pour supprimer les fichiers ")
    
    for (dir,n) in zip(dirs,range(len(dirs))):
        shutil.copytree(original_directory, dir)         #Copie le dossier original  
        directories.append(dir)
        modify_nparticles(dir, num_threads, input_file,n)  #Lance la fonction chargée de modifier le nombre de particule pour chaque dossier
    
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

    files_names=('depth-dose.dat','x-dose.dat','y-dose.dat','z-dose.dat')
    for name in files_names:
        file = [os.path.join(dir, name) for dir in directories]               #Récupère la position de chaque fichier 
        output_fused_file = os.path.join(original_directory, name)            #Produit la position du fichier fusioné
        fuse(file, output_fused_file, num_threads ,columns_to_add=[1, 2])                  #Produit le fichier fusioné

    return None


input_file= r'input.in'                              #Nom du fichier d'entré. Il est conseillé de ne pas le modifier et de changer le nom du fichier directement
command = r'.\penmain.exe < '+ input_file                         
directory = r'D:\Session Thom\Desktop\penelope\TP'        ########## A MODIFIER: emplacement du DOSSIER contenant tout les fichiers dont penmain.exe
threads = 1                                         ########## A MODIFIER: nombre de thread à utiliser. 

run_thread(command, directory, threads, input_file)                   #Lance le code
