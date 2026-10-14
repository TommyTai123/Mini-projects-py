import pygame
import sys
import gameplay.py

pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cyberpunk Hacker - Story Mode")

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
            
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN: # Nhấn phím Enter để bỏ qua cốt truyện
                # Chuyển cảnh! Gọi hàm start_game() từ file gameplay
                gameplay.start_game(screen) 
                
    screen.fill((0, 0, 0))
    # Code vẽ chữ chạy cốt truyện ở đây...
    
    pygame.display.flip()